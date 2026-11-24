import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from policy import assert_policy_participates


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workflow = self.root / ".github/workflows/all.yml"
        self.workflow.parent.mkdir(parents=True)
        self.valid = """name: all
on:
  push:
  pull_request:
  schedule:
    - cron: '17 6 * * *'
  workflow_dispatch:
permissions:
  contents: read
jobs:
  all:
    uses: nashspence/all/.github/workflows/policy.yml@main
"""
        self.restore()
        self.test_file = self.root / "test_repository.py"
        self.test_file.write_text("""import unittest
from all_policy import check_repository
class RepositoryTest(unittest.TestCase):
    def test_shared_policy(self):
        self.assertEqual(check_repository('.'), ())
""")
        import all_policy
        self.env = os.environ | {"PYTHONPATH": str(Path(all_policy.__file__).resolve().parent.parent)}

    def run_suite(self):
        return subprocess.run([sys.executable, "-m", "unittest", "discover"], cwd=self.root,
                              env=self.env, capture_output=True, text=True)

    def restore(self):
        self.workflow.write_text(self.valid)

    def probe(self):
        assert_policy_participates(self.run_suite, self.workflow.unlink, self.restore,
                                  ".github/workflows/all.yml: missing or unreadable")

    def test_existing_runner_observes_real_shared_policy(self):
        self.probe()

    def test_disconnected_test_is_detected_and_fixture_restored(self):
        self.test_file.write_text("import unittest\nclass ExistingTest(unittest.TestCase):\n    def test_existing_work(self):\n        self.assertTrue(True)\n")
        with self.assertRaisesRegex(AssertionError, "did not observe"):
            self.probe()
        self.assertEqual(self.workflow.read_text(), self.valid)

    def test_unrelated_failure_is_not_policy_participation(self):
        self.test_file.write_text("raise RuntimeError('unrelated')\n")
        with self.assertRaisesRegex(AssertionError, "baseline"):
            self.probe()
