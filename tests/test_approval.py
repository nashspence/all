import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from all_policy.performance import approval
from all_policy.performance.profiles import CORE


MAIN = "a" * 40
EVIDENCE = "b" * 40
WORKFLOW = ".github/workflows/core-profile-refresh.yml"
WORKFLOW_BYTES = b"name: core refresh\non: [workflow_dispatch]\n"
NOW = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def contents(data):
    if not isinstance(data, bytes):
        data = json.dumps(data, sort_keys=True).encode()
    return {"type": "file", "encoding": "base64", "sha": blob(data),
            "content": base64.b64encode(data).decode()}


class Authority:
    def __init__(self):
        digest = approval.source_digest()
        workflow_digest = hashlib.sha256(WORKFLOW_BYTES).hexdigest()
        self.registry = {"schema": 1, "profiles": {CORE: {
            "source_commit": MAIN, "source_digest": digest, "workflow": WORKFLOW,
            "workflow_digest": workflow_digest, "qualification_runs": [101, 102],
            "disposition": {"url": "https://github.com/nashspence/all/issues/69",
                            "reason": "Reviewed two-cohort qualification"}}}}
        self.index = {"schema": 1, "runs": []}
        self.runs = []
        self.first_attempts = {}
        for run_id, day in ((101, 25), (102, 26)):
            created = f"2026-11-{day}T09:00:00Z"
            completed = f"2026-11-{day}T09:05:00Z"
            self.runs.append({"id": run_id, "path": WORKFLOW, "head_branch": "main",
                              "head_sha": MAIN, "event": "workflow_dispatch",
                              "created_at": created, "status": "completed",
                              "conclusion": "success", "run_attempt": 1})
            self.index["runs"].append({
                "run_id": run_id, "workflow": WORKFLOW, "source_commit": MAIN,
                "source_digest": digest, "workflow_digest": workflow_digest,
                "run_attempt": 1, "event": "workflow_dispatch", "ref": "refs/heads/main",
                "created_at": created, "started_at": created, "completed_at": completed,
                "cohorts": [{"completed_at": completed, "workers": [
                    {"slot": slot, "runner_id": run_id * 100 + slot, "outcome": "pass"}
                    for slot in range(1, 13)]}],
                "evidence_path": f"runs/{run_id}.json", "evidence_sha256": "d" * 64})
        self.tree = {"truncated": False, "tree": [
            {"path": path, "type": "blob", "mode": "100644", "sha": blob(data)}
            for path, data in approval._source_files().items()]}
        self.requests = []

    def get(self, path, **query):
        self.requests.append((path, query))
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"type": "commit", "sha": MAIN}}
        if path.endswith("/git/ref/heads/profile-evidence"):
            return {"object": {"type": "commit", "sha": EVIDENCE}}
        if path.endswith("/contents/" + approval.REGISTRY_PATH):
            assert query == {"ref": MAIN}
            return contents(self.registry)
        if path.endswith("/contents/index.json"):
            assert query == {"ref": EVIDENCE}
            return contents(self.index)
        if path.endswith("/contents/" + WORKFLOW):
            assert query == {"ref": MAIN}
            return contents(WORKFLOW_BYTES)
        if path.endswith("/git/trees/" + MAIN):
            assert query == {"recursive": 1}
            return deepcopy(self.tree)
        if "/actions/workflows/" in path:
            assert query["branch"] == "main" and query["per_page"] == 100
            return {"total_count": len(self.runs), "workflow_runs": deepcopy(self.runs)}
        if path.endswith("/attempts/1"):
            return deepcopy(self.first_attempts[int(path.split("/")[-3])])
        if "/actions/runs/" in path:
            return deepcopy(next(run for run in self.runs if str(run["id"]) == path.rsplit("/", 1)[-1]))
        raise AssertionError((path, query))


class ApprovalTests(unittest.TestCase):
    def check(self, source, now=NOW):
        return approval._require_current({CORE}, source, now)

    def test_capacity_guard_cannot_be_used_to_discard_active_evidence(self):
        from all_policy.performance import refresh
        source = Authority()
        with patch.object(refresh, "MAX_ACTIVE_INDEX_BYTES", 1):
            with self.assertRaisesRegex(approval.ApprovalError, "reviewed epoch renewal"):
                self.check(source)
        with patch.object(refresh, "MAX_INDEX_BYTES", 1):
            with self.assertRaisesRegex(approval.ApprovalError, "publication capacity"):
                self.check(source)
        self.assertEqual(self.check(source)[CORE]["status"], "active")

    def test_current_authorities_are_pinned_and_live_history_is_required(self):
        source = Authority()
        result = self.check(source)[CORE]
        self.assertEqual(result["status"], "active")
        self.assertEqual((result["registry_commit"], result["evidence_commit"]), (MAIN, EVIDENCE))
        histories = [query for path, query in source.requests if "/actions/workflows/" in path]
        self.assertEqual(histories[0]["created"], ">=2026-11-25T09:00:00Z")
        source.runs.append(dict(source.runs[-1], id=103, created_at="2026-11-26T10:00:00Z",
                                status="completed", conclusion="cancelled"))
        with self.assertRaisesRegex(approval.ApprovalError, "suspended"):
            self.check(source)

    def test_expired_unknown_and_unapproved_implementation_do_not_accept(self):
        with self.assertRaisesRegex(approval.ApprovalError, "suspended"):
            self.check(Authority(), datetime(2026, 12, 7, tzinfo=timezone.utc))
        with self.assertRaisesRegex(approval.ApprovalError, "no current shared approval"):
            approval._require_current({"unknown"}, Authority(), NOW)
        source = Authority()
        source.registry["profiles"][CORE]["source_digest"] = "e" * 64
        with self.assertRaisesRegex(approval.ApprovalError, "not the approved implementation"):
            self.check(source)

    def test_rerun_cannot_replace_original_workers_but_outer_status_is_not_measurement(self):
        source = Authority()
        source.first_attempts[102] = dict(source.runs[-1], conclusion="failure")
        source.runs[-1]["run_attempt"] = 2
        entry = source.registry["profiles"][CORE]
        observed = approval._workflow_runs(source, entry, source.index, NOW)
        self.assertEqual((observed[-1]["run_attempt"], observed[-1]["conclusion"]), (1, "failure"))
        self.assertEqual(self.check(source)[CORE]["status"], "active")
        source.index["runs"][-1]["cohorts"][0]["workers"][0]["outcome"] = "failed"
        with self.assertRaisesRegex(approval.ApprovalError, "suspended"):
            self.check(source)
        source.first_attempts[102]["head_sha"] = "e" * 40
        with self.assertRaisesRegex(approval.ApprovalError, "original workflow attempt identity"):
            self.check(source)

    def test_current_main_code_workflow_and_qualification_provenance_are_bound(self):
        source = Authority()
        source.tree["tree"][0]["sha"] = "c" * 40
        with self.assertRaisesRegex(approval.ApprovalError, "current all/main implementation"):
            self.check(source)
        source = Authority()
        source.registry["profiles"][CORE]["workflow_digest"] = "f" * 64
        with self.assertRaisesRegex(approval.ApprovalError, "refresh workflow differs"):
            self.check(source)
        source = Authority()
        source.runs[0]["head_branch"] = "candidate"
        with self.assertRaisesRegex(approval.ApprovalError, "suspended"):
            self.check(source)

    def test_all_installed_python_sources_affect_digest_but_bytecode_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "__init__.py").write_text("")
            (package / "protocol.py").write_text("answer = 1\n")
            first = approval.source_digest(package_root=package)
            (package / "__pycache__").mkdir()
            (package / "__pycache__/protocol.pyc").write_bytes(b"compiled")
            self.assertEqual(first, approval.source_digest(package))
            (package / "protocol.py").write_text("answer = 2\n")
            self.assertNotEqual(first, approval.source_digest(package))
            (package / "new.py").write_text("new = True\n")
            self.assertNotEqual(first, approval.source_digest(package))

    def test_missing_ref_incomplete_tree_and_blob_mismatch_fail_closed(self):
        source = Authority()
        source.tree["truncated"] = True
        with self.assertRaisesRegex(approval.ApprovalError, "incomplete current shared source tree"):
            self.check(source)
        with self.assertRaisesRegex(approval.ApprovalError, "invalid shared authority ref"):
            approval._head(type("Missing", (), {"get": lambda *a, **k: {}})(), "main")
        wrong = contents(b"{}")
        wrong["sha"] = "0" * 40
        with self.assertRaisesRegex(approval.ApprovalError, "blob identity mismatch"):
            approval._content(type("Wrong", (), {"get": lambda *a, **k: wrong})(), "index.json", MAIN)

    def test_history_pagination_preserves_all_runs_and_rejects_api_cap(self):
        source = Authority()
        entry = source.registry["profiles"][CORE]
        rows = [dict(source.runs[-1], id=run_id) for run_id in range(101, 202)]
        class Pages:
            def get(self, path, **query):
                if "/actions/workflows/" not in path:
                    return source.get(path, **query)
                start = (query["page"] - 1) * 100
                return {"total_count": len(rows), "workflow_runs": rows[start:start + 100]}
        self.assertEqual(len(approval._workflow_runs(Pages(), entry, source.index, NOW)), 101)
        class Truncated(Pages):
            def get(self, path, **query):
                result = super().get(path, **query)
                if "total_count" in result:
                    result["total_count"] = 1000
                return result
        with self.assertRaisesRegex(approval.ApprovalError, "1,000-result"):
            approval._workflow_runs(Truncated(), entry, source.index, NOW)

    def test_durable_qualification_does_not_depend_on_expiring_old_actions_records(self):
        source = Authority()
        dates = ["2026-10-01", "2026-10-02", "2026-10-09", "2026-10-16",
                 "2026-10-23", "2026-10-30", "2026-11-06", "2026-11-13",
                 "2026-11-20", "2026-11-26"]
        template, metadata = deepcopy(source.index["runs"][0]), deepcopy(source.runs[0])
        source.index["runs"], source.runs = [], []
        for run_id, date in enumerate(dates, 101):
            created, completed = date + "T09:00:00Z", date + "T09:05:00Z"
            row = dict(deepcopy(template), run_id=run_id, created_at=created,
                       started_at=created, completed_at=completed, evidence_path=f"runs/{run_id}.json")
            row["cohorts"][0]["completed_at"] = completed
            for worker in row["cohorts"][0]["workers"]:
                worker["runner_id"] = run_id * 100 + worker["slot"]
            source.index["runs"].append(row)
            if date >= "2026-10-27":
                source.runs.append(dict(metadata, id=run_id, created_at=created))
        self.assertEqual(self.check(source)[CORE]["status"], "active")
        self.assertFalse(any("/actions/runs/" in path for path, _ in source.requests))
        history = next(query for path, query in source.requests if "/actions/workflows/" in path)
        self.assertEqual(history["created"], ">=2026-10-27T12:00:00Z")

    def test_transport_is_bounded_and_never_forwards_credentials_on_redirect(self):
        class Response(io.BytesIO):
            def geturl(self):
                return self.url
        class Opener:
            def __init__(self, data=b"{}", redirect=False, error=None):
                self.data, self.redirect, self.error, self.requests = data, redirect, error, []
            def open(self, request, timeout):
                self.requests.append((request, timeout))
                if self.error:
                    raise self.error
                result = Response(self.data)
                result.url = "https://elsewhere.invalid/" if self.redirect else request.full_url
                return result
        for opener, pattern in ((Opener(redirect=True), "redirects are forbidden"),
                                (Opener(b"x" * 9), "exceeds 2 MiB"),
                                (Opener(error=URLError("offline")), "unavailable"),
                                (Opener(error=HTTPError("https://api.github.com", 302, "redirect", {}, None)), "HTTP 302")):
            with self.subTest(pattern=pattern), patch.dict("os.environ", {"GH_TOKEN": "secret"}, clear=True), \
                    patch.object(approval, "build_opener", return_value=opener), patch.object(approval, "MAX_BYTES", 8):
                client = approval._GitHub()
                with self.assertRaisesRegex(approval.ApprovalError, pattern):
                    client.get(approval.PREFIX + "/git/ref/heads/main")
                self.assertEqual(len(opener.requests), 1)
                request, timeout = opener.requests[0]
                self.assertTrue(request.full_url.startswith("https://api.github.com/repos/nashspence/all/"))
                self.assertEqual((request.headers["Authorization"], timeout), ("Bearer secret", 10))
        self.assertIsNone(approval._NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.invalid"))
        with self.assertRaisesRegex(approval.ApprovalError, "duplicate key"):
            approval._json(b'{"schema":1,"schema":1}')

    def test_status_cli_reports_unavailable_with_no_cached_fallback(self):
        with patch.object(approval, "require_current", side_effect=approval.ApprovalError("expired")), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(approval.main([CORE]), 2)
            self.assertEqual(json.loads(output.getvalue()), {"status": "unavailable", "error": "expired"})
        with patch.object(approval, "_GitHub", side_effect=ValueError("invalid header: secret")):
            with self.assertRaises(approval.ApprovalError) as raised:
                approval.require_current({CORE})
            self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
