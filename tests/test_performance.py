"""Executable adoption example and controls for the actual outer timing boundary."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from all_policy.performance.contracts import BINDINGS_PATH, LIMITS_PATH, Limit, evaluate, load_authority
from all_policy.performance.profiles import CAPS_NS, CORE, DURABLE, NATIVE_SYNC, VOLATILE_SYNC, admit
from all_policy.performance.runner import run_suite


ADAPTER = '''from pathlib import Path
import time
def prepare(subject, work):
    return Path(work)
def run(work, repeat):
    if repeat == 1:
        time.sleep(0.12)
    (work / "result").write_text(str(repeat))
    return {"elapsed_ns": 1, "max_wall_ns": 999999999999999, "profile": "fake"}
def verify(work, result, repeat):
    return (work / "result").read_text() == str(repeat)
'''
COMMAND = '''from pathlib import Path
import sys
mode, work = sys.argv[1:]
path = Path(work) / "cold-result"
if mode == "run":
    path.write_text("complete")
elif mode == "verify":
    assert path.read_text() == "complete"
'''


def evidence(filesystem="ext4", options="rw,relatime", root="/work"):
    metadata = dict(system="Linux", machine="x86_64", python="3.11.9", logical_cpus=4,
                    affinity_count=4, memory_total_bytes=16 * 1024**3,
                    memory_max="max", cpu_max="max 100000", free_bytes=1024**3,
                    root=root, device=1, topology={"blockdevices": []},
                    mount={"fstype": filesystem, "source": "/dev/example", "options": options})
    return dict(metadata=metadata, metadata_after=copy.deepcopy(metadata), errors=[],
                samples_ns={name: [1_000_000] * 3 for name in CAPS_NS})


class CommonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.subject = self.root / "candidate"
        self.subject.mkdir()
        self.storage = self.root / "storage"
        self.storage.mkdir()
        subprocess.run(["git", "init", "-q", str(self.subject)], check=True)

    def commit(self):
        subprocess.run(["git", "-C", str(self.subject), "add", "--all"], check=True)
        subprocess.run(["git", "-C", str(self.subject), "-c", "user.name=Local Test",
                        "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], check=True)
        return subprocess.check_output(["git", "-C", str(self.subject), "rev-parse", "HEAD"], text=True).strip()

    def fixture(self, adapter=ADAPTER, command=COMMAND):
        for name, contents in (("adapter.py", adapter), ("command.py", command)):
            (self.subject / name).write_text(contents)
        digest = lambda name: hashlib.sha256((self.subject / name).read_bytes()).hexdigest()
        limits = {"schema": 1, "operations": {
            "cold": {"profile": CORE, "max_wall_ns": 1_000_000_000},
            "warm": {"profile": CORE, "max_wall_ns": 50_000_000}}}
        bindings = {"schema": 1, "repository": "nashspence/example", "operations": {
            "cold": {"mode": "command", "unit": "one complete process", "completion": "output closed",
                     "approved_files": {"command.py": digest("command.py")},
                     "command": ["{python}", "{subject}/command.py", "run", "{work}"],
                     "verify": ["{python}", "{subject}/command.py", "verify", "{work}"]},
            "warm": {"mode": "request", "unit": "one warm API operation",
                     "completion": "result file closed and all operation work returned",
                     "approved_files": {"adapter.py": digest("adapter.py")},
                     "adapter": "adapter.py", "cold_operation": "cold"}}}
        for name, document in ((LIMITS_PATH, limits), (BINDINGS_PATH, bindings)):
            path = self.subject / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document))
        revision = self.commit()
        return load_authority(self.subject, revision, "nashspence/example")

    def run_admitted(self, authority):
        with patch("all_policy.performance.runner._preflight", return_value=evidence()):
            return run_suite(authority, self.subject, {CORE: self.storage})

    def test_real_periodic_stall_cannot_be_hidden_by_candidate_time_or_budget_proposal(self):
        authority = self.fixture()
        path = self.subject / LIMITS_PATH
        proposal = json.loads(path.read_text())
        proposal["operations"]["warm"]["max_wall_ns"] = 999_999_999_999
        path.write_text(json.dumps(proposal))
        candidate = self.commit()
        approved = load_authority(self.subject, authority.revision, "nashspence/example")
        result = self.run_admitted(approved)
        self.assertEqual("miss", result["verdict"])
        self.assertNotIn("source_error", result)
        warm = result["operations"]["warm"]
        self.assertEqual(candidate, result["candidate_revision"])
        self.assertEqual("pass", result["operations"]["cold"]["decision"]["verdict"])
        self.assertEqual("miss", warm["decision"]["verdict"])
        self.assertEqual("mixed", warm["decision"]["miss_kind"])
        self.assertEqual(50_000_000, warm["decision"]["budget_ns"])
        self.assertLess(warm["decision"]["raw_min_ns"], 50_000_000)
        self.assertGreater(warm["decision"]["samples_ns"][1], 100_000_000)
        self.assertTrue(all(row["verified"] for row in warm["observations"]))
        self.assertEqual(3, len(warm["observations"]))
        self.assertGreater(warm["excluded_stages"]["startup_ns"], 0)
        self.assertGreater(warm["excluded_stages"]["drain_ns"], 0)

    def test_fast_wrong_output_is_failed_and_changed_adapter_needs_approval(self):
        authority = self.fixture(adapter=ADAPTER.replace("== str(repeat)", '== "wrong"'))
        result = self.run_admitted(authority)
        self.assertEqual("failed", result["operations"]["warm"]["decision"]["verdict"])
        (self.subject / "adapter.py").write_text(ADAPTER)
        self.commit()
        changed = self.run_admitted(authority)["operations"]["warm"]
        self.assertEqual("failed", changed["decision"]["verdict"])
        self.assertIn("independent approval", changed["excluded_stages"]["error"])
        self.assertEqual([], changed["observations"])

    def test_command_cannot_pass_while_descendant_continues_work(self):
        command = COMMAND.replace('path.write_text("complete")',
            'import subprocess\n    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"], start_new_session=True)\n    path.write_text("complete")')
        authority = self.fixture(command=command)
        start = time.monotonic()
        cold = self.run_admitted(authority)["operations"]["cold"]
        self.assertEqual("failed", cold["decision"]["verdict"])
        self.assertTrue(all(not row["completed"] for row in cold["observations"]))
        self.assertLess(time.monotonic() - start, 5)

    def test_untracked_and_ignored_helpers_cannot_be_attributed_to_candidate_commit(self):
        authority = self.fixture()
        (self.subject / ".gitignore").write_text("ignored.py\n")
        self.commit()
        for name in ("untracked.py", "ignored.py"):
            helper = self.subject / name
            helper.write_text("FAKE_PRODUCT = True\n")
            with patch("all_policy.performance.runner._preflight") as collect:
                result = run_suite(authority, self.subject, {CORE: self.storage})
            self.assertEqual("failed", result["verdict"])
            self.assertIn("unrecorded inputs", result["error"])
            collect.assert_not_called()
            helper.unlink()

    def test_product_source_mutation_cannot_be_attributed_to_the_original_revision(self):
        adapter = ADAPTER.replace('    return Path(work)',
            '    (Path(subject) / "product.txt").write_text("changed")\n    return Path(work)')
        authority = self.fixture(adapter=adapter.replace("time.sleep(0.12)", "time.sleep(0)"))
        (self.subject / "product.txt").write_text("original")
        self.commit()
        result = self.run_admitted(authority)
        self.assertTrue(all(row["decision"]["verdict"] == "pass" for row in result["operations"].values()))
        self.assertEqual("failed", result["verdict"])
        self.assertIn("source_error", result)

    def test_unqualified_environment_does_not_execute_candidate(self):
        authority = self.fixture()
        impaired = evidence()
        impaired["samples_ns"]["cpu_serial"][1] = CAPS_NS["cpu_serial"] + 1
        with patch("all_policy.performance.runner._preflight", return_value=impaired), patch("all_policy.performance.runner._measure") as run:
            result = run_suite(authority, self.subject, {CORE: self.storage})
        self.assertEqual("unqualified", result["verdict"])
        run.assert_not_called()

    def test_storage_claims_are_explicit_and_native_sync_never_promotes_to_persistence(self):
        native = evidence(options="rw,nobarrier,data=writeback,journal_async_commit,commit=30")
        self.assertTrue(admit(NATIVE_SYNC, native)["admitted"])
        self.assertFalse(admit(NATIVE_SYNC, native)["persistence_qualified"])
        self.assertFalse(admit(VOLATILE_SYNC, native)["admitted"])
        durable = admit(DURABLE, native)
        self.assertFalse(durable["admitted"])
        self.assertTrue(any("unsafe durability" in reason for reason in durable["reasons"]))
        native["approved_physical_storage"] = True
        self.assertFalse(admit(DURABLE, native)["admitted"])
        volatile = evidence(filesystem="tmpfs")
        self.assertTrue(admit(VOLATILE_SYNC, volatile)["admitted"])
        self.assertFalse(admit(NATIVE_SYNC, volatile)["admitted"])
        self.assertFalse(admit(DURABLE, evidence())["admitted"])

    def test_incomplete_or_incorrect_evidence_blocks_even_when_every_time_is_small(self):
        limit, admission = Limit(CORE, 50_000_000), {"profile": CORE, "admitted": True}
        valid = {"elapsed_ns": 1000, "completed": True, "verified": True}
        for rows in ([valid] * 2, [valid, valid, dict(valid, verified=False)],
                     [valid, valid, dict(valid, elapsed_ns=True)]):
            self.assertEqual("failed", evaluate(limit, admission, rows)["verdict"])


if __name__ == "__main__":
    unittest.main()
