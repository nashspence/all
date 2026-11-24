import base64
import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from all_policy.audit import AuditError, GitHub, audit
from all_policy.protocol import POLICY_PATH, SOURCE_REPOSITORY, WORKFLOW_PATH


NOW = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
CONSUMER = "nashspence/fishhat"


def caller(repository):
    reference = f"{SOURCE_REPOSITORY}/{POLICY_PATH}@main"
    if repository == SOURCE_REPOSITORY:
        reference = f"./{POLICY_PATH}"
    return f"""name: all
on:
  push:
  pull_request:
  workflow_dispatch:
  schedule:
    - cron: '17 3 * * *'
permissions:
  contents: read
jobs:
  all:
    uses: {reference}
"""


class FixtureGitHub(GitHub):
    def __init__(self):
        self.calls = []
        self.repositories = [
            {"full_name": name, "owner": {"login": "nashspence"},
             "default_branch": "main", "private": False, "archived": False, "fork": False}
            for name in (SOURCE_REPOSITORY, CONSUMER)
        ]
        self.responses = {
            "/user": {"login": "nashspence", "public_repos": 2, "owned_private_repos": 0},
            "/user/repos": self.repositories,
            "/users/nashspence/repos": self.repositories,
        }
        for index, repo in enumerate(self.repositories, 1):
            name = repo["full_name"]
            prefix = f"/repos/{name}"
            head = "policy-sha" if name == SOURCE_REPOSITORY else "consumer-sha"
            run = {
                "id": index, "head_sha": head, "head_branch": "main", "event": "schedule",
                "run_attempt": 1, "status": "completed", "conclusion": "success",
                "run_started_at": (NOW - timedelta(hours=12)).isoformat(),
                "created_at": (NOW - timedelta(hours=12)).isoformat(),
                "referenced_workflows": [{"path": f"{SOURCE_REPOSITORY}/{POLICY_PATH}@main", "sha": "policy-sha"}],
            }
            self.responses[f"{prefix}/git/ref/heads/main"] = {"object": {"sha": head}}
            self.responses[f"{prefix}/contents/{WORKFLOW_PATH}"] = {
                "encoding": "base64", "content": base64.encodebytes(caller(name).encode()).decode(),
            }
            self.responses[f"{prefix}/actions/workflows/all.yml"] = {"state": "active", "path": WORKFLOW_PATH}
            self.responses[f"{prefix}/actions/workflows/all.yml/runs"] = {"workflow_runs": [run]}
            self.responses[f"{prefix}/actions/runs/{index}"] = run
            self.responses[f"{prefix}/actions/runs/{index}/attempts/1/jobs"] = {
                "jobs": [{"name": "all / check", "status": "completed", "conclusion": "success"}],
            }

    def get(self, path, **query):
        self.calls.append((path, query))
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value()
        return copy.deepcopy(value)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.client = FixtureGitHub()
        self.run = self.client.responses[f"/repos/{CONSUMER}/actions/runs/2"]

    def audit(self, **kwargs):
        return audit("nashspence", client=self.client, now=NOW,
                     inventory_token=kwargs.pop("inventory_token", "test-token"), **kwargs)

    def errors(self, name=CONSUMER, **kwargs):
        return " ".join(error for result in self.audit(**kwargs)
                        if result.repository == name for error in result.errors)

    def test_current_successful_self_and_consumer_pass(self):
        results = self.audit()
        self.assertEqual({result.repository for result in results}, {SOURCE_REPOSITORY, CONSUMER})
        self.assertTrue(all(not result.errors for result in results))
        self.assertIn((f"/repos/{CONSUMER}/contents/{WORKFLOW_PATH}", {"ref": "consumer-sha"}), self.client.calls)

    def test_same_named_tags_cannot_shadow_default_or_policy_branches(self):
        for name in (SOURCE_REPOSITORY, CONSUMER):
            self.client.responses[f"/repos/{name}/commits/main"] = {"sha": "tag-sha"}
        self.assertTrue(all(not result.errors for result in self.audit()))

    def test_public_fallback_audits_repositories_but_never_certifies_complete_inventory(self):
        results = self.audit(inventory_token=None)
        self.assertEqual(len(results), 3)
        self.assertIn("ALL_REPOS_TOKEN", results[0].errors[0])
        self.assertTrue(all(not result.errors for result in results[1:]))
        self.assertNotIn("/user", [path for path, query in self.client.calls])

    def test_token_for_another_owner_fails_and_only_reads_public_inventory(self):
        self.client.responses["/user"]["login"] = "someone-else"
        self.assertIn("must belong", self.errors("nashspence (inventory)"))
        self.assertNotIn("/user/repos", [path for path, query in self.client.calls])

    def test_missing_or_restricted_private_inventory_fails(self):
        for count in (None, 1):
            with self.subTest(count=count):
                self.client.responses["/user"]["owned_private_repos"] = count
                self.assertIn("incomplete inventory", self.errors("nashspence (inventory)"))

    def test_restricted_public_inventory_fails(self):
        self.client.responses["/user"]["public_repos"] = 3
        self.assertIn("public_repos=3, visible=2", self.errors("nashspence (inventory)"))

    def test_archived_and_forked_repositories_are_not_exempt(self):
        self.client.repositories[1].update(archived=True, fork=True)
        self.client.responses[f"/repos/{CONSUMER}/contents/{WORKFLOW_PATH}"] = AuditError("GitHub HTTP 404")
        self.assertIn("404", self.errors())

    def test_other_owners_are_excluded(self):
        self.client.repositories.append({"full_name": "someone/else", "owner": {"login": "someone"}})
        self.assertTrue(all(not result.errors for result in self.audit()))

    def test_missing_workflow_fails_without_hiding_siblings(self):
        self.client.responses[f"/repos/{CONSUMER}/contents/{WORKFLOW_PATH}"] = AuditError("GitHub HTTP 404")
        results = self.audit()
        self.assertTrue(next(result for result in results if result.repository == CONSUMER).errors)
        self.assertFalse(next(result for result in results if result.repository == SOURCE_REPOSITORY).errors)

    def test_invalid_configuration_cannot_pass_on_old_green_results(self):
        self.client.responses[f"/repos/{CONSUMER}/contents/{WORKFLOW_PATH}"]["content"] = base64.b64encode(b"name: incomplete\n").decode()
        self.assertTrue(self.errors())

    def test_disabled_workflow_fails(self):
        self.client.responses[f"/repos/{CONSUMER}/actions/workflows/all.yml"]["state"] = "disabled_inactivity"
        self.assertIn("not active", self.errors())

    def test_old_head_wrong_branch_and_pull_request_runs_cannot_certify_default_head(self):
        for field, value in (("head_sha", "old-sha"), ("head_branch", "feature"), ("event", "pull_request")):
            with self.subTest(field=field):
                original = self.run[field]
                self.run[field] = value
                self.assertIn("no policy run", self.errors())
                self.run[field] = original

    def test_newest_failure_or_pending_run_wins_over_older_success(self):
        for status, conclusion in (("completed", "failure"), ("queued", None), ("completed", "cancelled")):
            with self.subTest(status=status, conclusion=conclusion):
                newest = dict(self.run, id=3, status=status, conclusion=conclusion)
                self.client.responses[f"/repos/{CONSUMER}/actions/workflows/all.yml/runs"] = {"workflow_runs": [self.run, newest]}
                self.client.responses[f"/repos/{CONSUMER}/actions/runs/3"] = newest
                self.client.responses[f"/repos/{CONSUMER}/actions/runs/3/attempts/1/jobs"] = {"jobs": []}
                self.assertIn("latest policy run is not successful", self.errors())

    def test_pending_run_without_a_timestamp_is_a_failure(self):
        self.run.update(status="queued", conclusion=None, run_started_at=None)
        self.assertIn("latest policy run is not successful", self.errors())

    def test_newer_failed_attempt_of_an_older_run_wins_over_newer_id_success(self):
        rerun = dict(self.run, id=1, run_attempt=2, conclusion="failure",
                     run_started_at=(NOW - timedelta(hours=1)).isoformat())
        self.client.responses[f"/repos/{CONSUMER}/actions/workflows/all.yml/runs"] = {"workflow_runs": [self.run, rerun]}
        self.client.responses[f"/repos/{CONSUMER}/actions/runs/1"] = rerun
        self.client.responses[f"/repos/{CONSUMER}/actions/runs/1/attempts/2/jobs"] = {"jobs": []}
        self.assertIn("latest policy run is not successful", self.errors())

    def test_missing_or_invalid_ordering_evidence_cannot_hide_a_failure(self):
        for timestamp in (None, "invalid", "2026-11-24T11:00:00"):
            with self.subTest(timestamp=timestamp):
                unknown = dict(self.run, id=1, conclusion="failure", run_started_at=timestamp)
                self.client.responses[f"/repos/{CONSUMER}/actions/workflows/all.yml/runs"] = {"workflow_runs": [self.run, unknown]}
                self.assertIn("cannot order policy runs", self.errors())

    def test_malformed_run_is_a_failure_without_hiding_siblings(self):
        self.client.responses[f"/repos/{CONSUMER}/actions/runs/2"] = None
        results = self.audit()
        self.assertTrue(next(result for result in results if result.repository == CONSUMER).errors)
        self.assertFalse(next(result for result in results if result.repository == SOURCE_REPOSITORY).errors)

    def test_stale_missing_and_foreign_policy_provenance_fail(self):
        references = [[], [{"path": f"{SOURCE_REPOSITORY}/{POLICY_PATH}@main", "sha": "old-policy"}],
                      [{"path": f"someone/else/{POLICY_PATH}@main", "sha": "policy-sha"}]]
        for value in references:
            with self.subTest(value=value):
                self.run["referenced_workflows"] = value
                self.assertIn("current all/main policy commit", self.errors())

    def test_local_provenance_is_accepted_only_for_the_source_repository(self):
        self_run = self.client.responses[f"/repos/{SOURCE_REPOSITORY}/actions/runs/1"]
        self_run["referenced_workflows"][0]["path"] = f"./{POLICY_PATH}@refs/heads/main"
        self.assertFalse(self.errors(SOURCE_REPOSITORY))
        self.run["referenced_workflows"][0]["path"] = f"./{POLICY_PATH}@refs/heads/main"
        self.assertIn("current all/main policy commit", self.errors())

    def test_stale_and_future_results_fail(self):
        for age in (timedelta(hours=49), timedelta(minutes=-6)):
            with self.subTest(age=age):
                self.run["run_started_at"] = (NOW - age).isoformat()
                self.assertIn("not fresh", self.errors())

    def test_skipped_failed_and_missing_policy_job_fail_even_if_workflow_is_green(self):
        path = f"/repos/{CONSUMER}/actions/runs/2/attempts/1/jobs"
        for jobs in ([], [{"name": "all / check", "status": "completed", "conclusion": "skipped"}],
                     [{"name": "all / check", "status": "completed", "conclusion": "failure"}]):
            with self.subTest(jobs=jobs):
                self.client.responses[path] = {"jobs": jobs}
                self.assertIn("all / check did not complete successfully", self.errors())

    def test_latest_attempt_is_checked(self):
        self.run["run_attempt"] = 2
        self.client.responses[f"/repos/{CONSUMER}/actions/runs/2/attempts/2/jobs"] = {"jobs": []}
        self.assertIn("did not complete successfully", self.errors())

    def test_head_change_during_audit_fails(self):
        values = iter([{"object": {"sha": "consumer-sha"}}, {"object": {"sha": "new-head"}}])
        self.client.responses[f"/repos/{CONSUMER}/git/ref/heads/main"] = lambda: next(values)
        self.assertIn("default branch changed", self.errors())

    def test_policy_change_during_audit_fails(self):
        values = iter([{"object": {"sha": "policy-sha"}}] * 3 + [{"object": {"sha": "new-policy"}}])
        self.client.responses[f"/repos/{SOURCE_REPOSITORY}/git/ref/heads/main"] = lambda: next(values)
        self.assertIn("all/main changed", self.errors(SOURCE_REPOSITORY))

    def test_run_attempt_change_during_audit_fails(self):
        values = iter([self.run, dict(self.run, run_attempt=2, status="in_progress", conclusion=None)])
        self.client.responses[f"/repos/{CONSUMER}/actions/runs/2"] = lambda: next(values)
        self.assertIn("policy run changed", self.errors())

    def test_inventory_and_source_api_errors_are_failures(self):
        for path in ("/user/repos", f"/repos/{SOURCE_REPOSITORY}/git/ref/heads/main"):
            with self.subTest(path=path):
                original = self.client.responses[path]
                self.client.responses[path] = AuditError("GitHub HTTP 403")
                self.assertTrue(any(result.errors for result in self.audit()))
                self.client.responses[path] = original


class GitHubTests(unittest.TestCase):
    def test_malformed_pages_are_api_errors(self):
        for value in (None, [], {}, {"jobs": None}, {"jobs": "invalid"}):
            with self.subTest(value=value):
                client = GitHub()
                with patch.object(client, "get", return_value=value):
                    with self.assertRaises(AuditError):
                        list(client.pages("/resource", key="jobs"))

    def test_pagination_includes_the_last_repository_and_job(self):
        for key in (None, "jobs"):
            with self.subTest(key=key):
                client = GitHub()
                pages = [list(range(100)), [100]]
                if key:
                    pages = [{key: page} for page in pages]
                with patch.object(client, "get", side_effect=pages) as get:
                    self.assertEqual(list(client.pages("/resource", key=key)), list(range(101)))
                self.assertEqual(get.call_args_list[1].kwargs["page"], 2)

    def test_http_and_network_errors_never_expose_credentials(self):
        for error in (HTTPError("https://api.github.com", 403, "Forbidden", {}, None), URLError("network unavailable")):
            with self.subTest(error=error), patch("all_policy.audit.urlopen", side_effect=error):
                with self.assertRaises(AuditError) as raised:
                    GitHub("secret-token").get("/resource")
                self.assertNotIn("secret-token", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
