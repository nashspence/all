"""Focused collector deadline, partial-evidence and no-approval checks."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from all_policy.performance import qualify_storage as qualification


class StorageQualificationTests(unittest.TestCase):
    def test_deadline_retains_valid_partial_observations_and_stops_waiting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "packet.json"
            packet = {"schema": qualification.SCHEMA, "root": str(root),
                      "profile_approved": False, "physical_persistence_proven": False,
                      "status": "collecting", "errors": [],
                      "progress": {"stage": "execute", "operation": "atomic16_p1", "repeat": 1},
                      "operations": {"atomic16_p1": {"observations": [
                          {"elapsed_ns": 1234567, "verified": True, "error": None},
                          {"elapsed_ns": None, "verified": False, "error": None}]}}}
            code = ("import json,time; print(" + repr(json.dumps({"record": packet, "complete": False})) +
                    ",flush=True); time.sleep(60)")
            with patch.object(qualification, "_child_command", return_value=[sys.executable, "-u", "-c", code]), contextlib.redirect_stdout(io.StringIO()):
                started = time.monotonic()
                exit_code = qualification.main(["--root", str(root), "--output", str(output), "--timeout-seconds", "0.3"])
                elapsed = time.monotonic() - started
            evidence = json.loads(output.read_text())
            self.assertEqual(exit_code, 3)
            self.assertLess(elapsed, 2)
            self.assertEqual(evidence["status"], "collection_failed")
            self.assertTrue(evidence["coordinator"]["timed_out"])
            self.assertFalse(evidence["coordinator"]["complete"])
            self.assertFalse(evidence["profile_approved"])
            observations = evidence["operations"]["atomic16_p1"]["observations"]
            self.assertEqual(observations[0], packet["operations"]["atomic16_p1"]["observations"][0])
            self.assertIsNone(observations[1]["elapsed_ns"])
            self.assertIn("TimeoutError", observations[1]["error"])

    def test_completed_screen_cannot_approve_and_existing_packet_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "packet.json"
            record = {"schema": qualification.SCHEMA, "root": str(root),
                      "profile_approved": False, "physical_persistence_proven": False,
                      "status": "screen_pass_pending_shared_review", "errors": [], "operations": {}}
            code = "print(" + repr(json.dumps({"record": record, "complete": True})) + ",flush=True)"
            with patch.object(qualification, "_child_command", return_value=[sys.executable, "-u", "-c", code]), contextlib.redirect_stdout(io.StringIO()):
                exit_code = qualification.main(["--root", str(root), "--output", str(output)])
            evidence = json.loads(output.read_text())
            self.assertEqual(exit_code, 2)
            self.assertTrue(evidence["coordinator"]["complete"])
            self.assertFalse(evidence["profile_approved"])
            before = output.read_bytes()
            with patch.object(qualification, "_child_command", side_effect=AssertionError("must not start a worker")), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(qualification.main(["--root", str(root), "--output", str(output)]), 3)
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
