import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

from all_policy.performance import publish_refresh as publication
from all_policy.performance import refresh


SOURCE = "a" * 40
DIGEST = "b" * 64
WORKFLOW = ".github/workflows/core-profile-refresh.yml"
WORKFLOW_BYTES = b"reviewed main workflow\n"
WORKFLOW_DIGEST = hashlib.sha256(WORKFLOW_BYTES).hexdigest()
NOW = "2026-11-27T01:05:00Z"


class CampaignClient:
    def __init__(self):
        self.run = {"id": 41, "run_attempt": 1, "head_branch": "main", "path": WORKFLOW,
                    "head_sha": SOURCE, "event": "push", "repository": {"full_name": "nashspence/all"},
                    "head_repository": {"full_name": "nashspence/all"},
                    "created_at": "2026-11-27T01:00:00Z", "run_started_at": "2026-11-27T01:00:01Z"}
        self.jobs = [{"id": 1000 + slot, "name": f"core-1-{slot}", "runner_id": 2000 + slot,
                      "runner_name": f"runner-{slot}", "status": "completed", "conclusion": "success",
                      "completed_at": "2026-11-27T01:04:00Z",
                      "steps": [{"name": "Upload retained evidence", "conclusion": "success"}]}
                     for slot in range(1, 13)]

    def get(self, path, **query):
        if path.endswith("/actions/runs/41"):
            return deepcopy(self.run)
        if path.endswith("/contents/" + WORKFLOW):
            return {"encoding": "base64", "content": base64.b64encode(WORKFLOW_BYTES).decode()}
        raise AssertionError(path)

    def first_attempt_jobs(self, run_id):
        self.requested_attempt = (run_id, 1)
        return deepcopy(self.jobs)


class BranchClient:
    """A Git-shaped CAS store; a racing sibling cannot fast-forward our parent."""
    def __init__(self):
        self.head = None
        self.blobs, self.trees, self.commits = {}, {}, {}
        self.writes = []
        self.race = None
        self.history, self.original_runs, self.jobs_by_run = [], {}, {}
        self.registry = {"schema": 1, "profiles": {}}

    @staticmethod
    def missing():
        return HTTPError("https://api.github.com/example", 404, "missing", {}, None)

    def get(self, path, **query):
        if "/actions/workflows/" in path:
            return {"workflow_runs": deepcopy(self.history), "total_count": len(self.history)}
        if "/actions/runs/" in path:
            return deepcopy(self.original_runs[int(path.split("/actions/runs/", 1)[1].split("/", 1)[0])])
        if "/git/ref/" in path:
            if self.head is None:
                raise self.missing()
            return {"object": {"sha": self.head}}
        if "/git/commits/" in path:
            commit = self.commits[path.rsplit("/", 1)[1]]
            return {"tree": {"sha": commit["tree"]}}
        if "/contents/" in path:
            name = path.split("/contents/", 1)[1]
            if name == ".all/performance/approvals.json":
                raw = publication._encode(self.registry)
            else:
                tree = self.trees[self.commits[query["ref"]]["tree"]]
                if name not in tree:
                    raise self.missing()
                raw = self.blobs[tree[name]]
            identity = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            return {"type": "file", "sha": identity, "encoding": "base64",
                    "content": base64.b64encode(raw).decode()}
        raise AssertionError(path)

    def first_attempt_jobs(self, run_id):
        return deepcopy(self.jobs_by_run[run_id])

    def request(self, method, path, data):
        self.writes.append((method, path, deepcopy(data)))
        if path.endswith("/git/blobs"):
            raw = base64.b64decode(data["content"])
            identity = hashlib.sha1(raw).hexdigest()
            self.blobs[identity] = raw
            return {"sha": identity}
        if path.endswith("/git/trees"):
            tree = deepcopy(self.trees.get(data.get("base_tree"), {}))
            tree.update({row["path"]: row["sha"] for row in data["tree"]})
            identity = hashlib.sha1(publication._encode(tree)).hexdigest()
            self.trees[identity] = tree
            return {"sha": identity}
        if path.endswith("/git/commits"):
            identity = hashlib.sha1(publication._encode(data)).hexdigest()
            self.commits[identity] = deepcopy(data)
            return {"sha": identity}
        if "/git/refs" in path:
            if self.race is not None:
                callback, self.race = self.race, None
                callback()
            candidate = self.commits[data["sha"]]
            if method == "PATCH":
                self.assert_not_forced = data["force"] is False
                if candidate["parents"] != [self.head]:
                    raise HTTPError("https://api.github.com/example", 422, "not fast forward", {}, None)
            elif self.head is not None:
                raise HTTPError("https://api.github.com/example", 422, "already exists", {}, None)
            self.head = data["sha"]
            return {"object": {"sha": self.head}}
        raise AssertionError((method, path))

    def index(self):
        tree = self.trees[self.commits[self.head]["tree"]]
        return json.loads(self.blobs[tree["index.json"]])


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.client = CampaignClient()
        self.environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "nashspence/all",
                            "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ATTEMPT": "1",
                            "GITHUB_EVENT_NAME": "push", "GITHUB_RUN_ID": "41",
                            "GITHUB_SHA": SOURCE, "GITHUB_WORKFLOW_SHA": SOURCE}
        for slot in range(1, 13):
            self.write(slot)

    def write(self, number, **changes):
        packet = {"schema": 1, "run_id": 41, "run_attempt": 1, "cohort": 1, "slot": number,
                  "source_commit": SOURCE, "source_digest": DIGEST, "workflow_sha": SOURCE,
                  "runner_name": f"runner-{number}", "outcome": "pass", "raw": {"elapsed_ns": [3, 5, 7]}}
        packet.update(changes)
        path = self.directory / f"worker-1-{number}.json"
        path.write_text(json.dumps(packet) + "\n")
        return path

    def collect(self, **changes):
        kwargs = {"reports": self.directory, "kind": "core", "source": SOURCE,
                  "source_digest": DIGEST, "workflow": WORKFLOW, "workflow_digest": WORKFLOW_DIGEST,
                  "environment": self.environment, "now": NOW,
                  "classifier": lambda packet, kind, digest: packet["outcome"],
                  "artifact_verifier": lambda *args, **kwargs: ([], {})}
        kwargs.update(changes)
        return publication.collect(self.client, **kwargs)

    def test_original_job_inventory_and_expiring_verification_report(self):
        path = self.write(4, outcome="environment")
        summary, raw = self.collect()
        self.assertEqual(self.client.requested_attempt, (41, 1))
        self.assertEqual(summary["cohorts"][0]["workers"][3],
                         {"slot": 4, "runner_id": 2004, "outcome": "environment"})
        self.assertEqual(summary["cohorts"][0]["completed_at"], "2026-11-27T01:04:00Z")
        retained = json.loads(raw)["reports"][path.name]
        self.assertNotIn("base64", retained)
        self.assertEqual(retained["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(retained["bytes"], len(path.read_bytes()))
        reports, _, _ = publication.read_reports(self.directory)
        self.assertEqual(base64.b64decode(reports[path.name]["base64"]), path.read_bytes())
        self.assertEqual(summary["evidence_sha256"], hashlib.sha256(raw).hexdigest())

    def test_missing_jobs_missing_packets_and_false_success_are_not_environment(self):
        self.client.jobs = self.client.jobs[1:]
        (self.directory / "worker-1-2.json").unlink()
        self.client.jobs[1]["steps"][0]["conclusion"] = "failure"
        self.client.jobs[2]["conclusion"] = "failure"
        self.write(5, source_commit="c" * 40)
        summary, raw = self.collect()
        workers = summary["cohorts"][0]["workers"]
        self.assertEqual([row["outcome"] for row in workers[:5]], ["incomplete"] * 5)
        self.assertEqual(workers[0]["runner_id"], 0)
        self.assertEqual(len(workers), 12)
        self.assertGreaterEqual(len(json.loads(raw)["errors"]), 5)

    def test_duplicate_report_and_malformed_json_remain_visible(self):
        duplicate = self.directory / "another-artifact"
        duplicate.mkdir()
        (duplicate / "worker-1-1.json").write_bytes((self.directory / "worker-1-1.json").read_bytes())
        (self.directory / "worker-1-2.json").write_text('{"schema":1,"schema":1}')
        self.write(3, slot=True)
        summary, raw = self.collect()
        self.assertEqual([row["outcome"] for row in summary["cohorts"][0]["workers"][:3]],
                         ["incomplete"] * 3)
        self.assertEqual(len(json.loads(raw)["reports"]), 13)

    def test_failed_original_worker_cannot_be_substituted_or_relabelled(self):
        self.write(7, outcome="failed")
        self.client.jobs[6]["conclusion"] = "failure"
        summary, _ = self.collect()
        self.assertEqual(summary["cohorts"][0]["workers"][6]["outcome"], "failed")
        self.environment["GITHUB_RUN_ATTEMPT"] = "2"
        with self.assertRaises(publication.PublicationError):
            self.collect()
        self.environment["GITHUB_RUN_ATTEMPT"] = "1"
        self.client.run["head_branch"] = "other"
        with self.assertRaises(publication.PublicationError):
            self.collect()

    def test_branch_appends_preserve_immutable_evidence_and_reject_replacement(self):
        summary, raw = self.collect()
        branch = BranchClient()
        original = publication.append(branch, summary, raw)
        with self.assertRaisesRegex(publication.PublicationError, "already recorded"):
            publication.append(branch, summary, raw)
        later = deepcopy(summary)
        later.update(run_id=42, evidence_path="runs/42.json")
        later["evidence_sha256"] = hashlib.sha256(b"second original record\n").hexdigest()
        publication.append(branch, later, b"second original record\n")
        self.assertTrue(branch.assert_not_forced)
        self.assertEqual(branch.commits[branch.head]["parents"], [original])
        self.assertEqual([row["run_id"] for row in branch.index()["runs"]], [41, 42])
        tree = branch.trees[branch.commits[branch.head]["tree"]]
        self.assertEqual(json.loads(branch.blobs[tree["runs/41.json"]]), summary)
        self.assertEqual(len(tree), 3)
        self.assertNotIn(raw, branch.blobs.values())
        self.assertTrue(all(b'"base64"' not in value for value in branch.blobs.values()))

    def test_concurrent_append_rebases_on_new_history_without_losing_either_run(self):
        summary, raw = self.collect()
        branch = BranchClient()
        publication.append(branch, summary, raw)
        second, third = deepcopy(summary), deepcopy(summary)
        second.update(run_id=42, evidence_path="runs/42.json")
        third.update(run_id=43, evidence_path="runs/43.json")
        branch.race = lambda: publication.append(branch, second, raw)
        publication.append(branch, third, raw)
        self.assertEqual([row["run_id"] for row in branch.index()["runs"]], [41, 42, 43])
        self.assertTrue(branch.assert_not_forced)

    def test_lost_original_publisher_is_durable_even_after_api_history_expires(self):
        summary, raw = self.collect()
        branch = BranchClient()
        original = deepcopy(self.client.run)
        original.update(id=40, status="completed", conclusion="failure",
                        created_at="2026-11-26T01:00:00Z", run_started_at="2026-11-26T01:00:01Z",
                        updated_at="2026-11-26T01:05:00Z")
        branch.original_runs[40] = original
        branch.jobs_by_run[40] = []
        rerun = deepcopy(original)
        rerun.update(run_attempt=2, conclusion="success")
        branch.history = [rerun]
        publication.append(branch, summary, raw)
        lost, current = branch.index()["runs"]
        self.assertEqual([lost["run_id"], current["run_id"]], [40, 41])
        self.assertEqual(lost["source_digest"], "0" * 64)
        self.assertEqual({worker["outcome"] for worker in lost["cohorts"][0]["workers"]}, {"incomplete"})
        first_tree = branch.trees[branch.commits[branch.head]["tree"]]
        retained = branch.blobs[first_tree["runs/40.json"]]
        self.assertEqual(json.loads(retained), lost)
        branch.history = []
        later = deepcopy(summary)
        later.update(run_id=42, evidence_path="runs/42.json")
        publication.append(branch, later, raw)
        self.assertEqual([row["run_id"] for row in branch.index()["runs"]], [40, 41, 42])
        last_tree = branch.trees[branch.commits[branch.head]["tree"]]
        self.assertEqual(branch.blobs[last_tree["runs/40.json"]], retained)

    def test_artifact_mismatch_retains_raw_packet_and_marks_its_allocation_incomplete(self):
        summary, raw = self.collect(artifact_verifier=lambda *args, **kwargs:
                                   ([{"id": 51, "status": "failed", "error": "digest mismatch"}],
                                    {(1, 6): "digest mismatch"}))
        workers = summary["cohorts"][0]["workers"]
        self.assertEqual(workers[5]["outcome"], "incomplete")
        self.assertEqual(sum(row["outcome"] == "pass" for row in workers), 11)
        self.assertIn("worker-1-6.json", json.loads(raw)["reports"])
        self.assertEqual(json.loads(raw)["artifacts"][0]["status"], "failed")

    def test_compacted_receipt_still_prevents_replay(self):
        summary, raw = self.collect()
        branch = BranchClient()
        publication.append(branch, summary, raw)
        later = deepcopy(summary)
        later.update(run_id=42, evidence_path="runs/42.json",
                     created_at="2027-01-10T01:00:00Z", started_at="2027-01-10T01:00:01Z",
                     completed_at="2027-01-10T01:05:00Z")
        later["cohorts"][0]["completed_at"] = "2027-01-10T01:04:00Z"
        publication.append(branch, later, raw)
        self.assertEqual([row["run_id"] for row in branch.index()["runs"]], [42])
        with self.assertRaisesRegex(publication.PublicationError, "already recorded"):
            publication.append(branch, summary, raw)

    def test_capacity_refuses_before_writing_any_git_objects(self):
        summary, raw = self.collect()
        branch = BranchClient()
        with patch.object(refresh, "MAX_INDEX_BYTES", 1):
            with self.assertRaisesRegex(publication.PublicationError, "index capacity exhausted"):
                publication.append(branch, summary, raw)
        self.assertEqual(branch.writes, [])
        self.assertIsNone(branch.head)

    def test_two_environmental_rejections_publish_then_fail_availability(self):
        self.write(1, outcome="environment")
        self.write(2, outcome="environment")
        summary, raw = self.collect()
        arguments = ["--reports", str(self.directory), "--kind", "core", "--source", SOURCE,
                     "--source-digest", DIGEST, "--workflow", WORKFLOW,
                     "--workflow-digest", WORKFLOW_DIGEST,
                     "--verification-report", str(self.directory / "verification.json")]
        with patch.object(publication, "GitHub", return_value=object()), \
                patch.object(publication, "collect", return_value=(summary, raw)), \
                patch.object(publication, "append", return_value=SOURCE) as append, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(publication.main(arguments), 1)
        append.assert_called_once()
        self.assertEqual((self.directory / "verification.json").read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
