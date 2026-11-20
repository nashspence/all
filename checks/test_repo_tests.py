import subprocess
import tempfile
import unittest
from pathlib import Path

from make_help import Pin
from repo_tests import PRESS, TEST_FILE, check, tracked_blob


ISSUE = "nashspence/all#14"
WORKFLOW = f"""on: pull_request
jobs:
  {PRESS.job}:
    steps:
      - run: {PRESS.command}
""".encode()
MAKEFILE = b"""PYTHON := mise exec -- uv run --locked python
ifneq ($(filter setup,$(MAKECMDGOALS)),)
else
test: ## Run the suite.
	@$(PYTHON) -m unittest discover -s tests
endif
"""
BASE = b"""import unittest

class PublisherTests(unittest.TestCase):
    def test_existing(self):
        self.assertTrue(True)
"""
METHOD = b"""
    def test_make_help_works_before_setup(self):
        self.assertIn("setup", "make setup")
"""


class RepoTests(unittest.TestCase):
    def test_only_absent_case_is_xfail(self):
        notes, errors = check(WORKFLOW, MAKEFILE, BASE, expected=ISSUE)
        self.assertEqual(errors, [])
        self.assertIn("XFAIL", notes[0])
        self.assertIn(ISSUE, notes[0])
        self.assertIn("FAIL", check(WORKFLOW, MAKEFILE, BASE)[1][0])

    def test_correct_wiring_and_present_case_are_strict_xpass_until_exception_removed(self):
        self.assertIn("XPASS", check(WORKFLOW, MAKEFILE, BASE + METHOD, expected=ISSUE)[1][0])
        self.assertEqual(check(WORKFLOW, MAKEFILE, BASE + METHOD), ([], []))

    def test_requires_pr_lane_even_while_case_is_missing(self):
        for workflow in (
            WORKFLOW.replace(b"pull_request", b"push"),
            WORKFLOW.replace(b"run: make test", b"name: make test"),
            WORKFLOW + b"        if: false\n",
            b"jobs: [",
        ):
            with self.subTest(workflow=workflow):
                notes, errors = check(workflow, MAKEFILE, BASE, expected=ISSUE)
                self.assertEqual(notes, [])
                self.assertTrue(errors[0].startswith("FAIL "))

    def test_requires_make_discovery_even_while_case_is_missing(self):
        for makefile in (
            MAKEFILE.replace(b"discover -s tests", b"discover -s another_directory"),
            MAKEFILE.replace(b"discover -s tests", b"discover -s tests -p nonexistent.py"),
            MAKEFILE.replace(b"@$(PYTHON)", b"@echo $(PYTHON)"),
            MAKEFILE.replace(b"else\n", b""),
            MAKEFILE.replace(b"endif\n", b""),
            MAKEFILE.replace(b"test:", b"test: extra-tests"),
            MAKEFILE.replace(b"@$(PYTHON)", b"@-$(PYTHON)"),
            MAKEFILE.replace(b"PYTHON := mise", b"PYTHON := echo mise"),
            MAKEFILE + b".IGNORE: test another-test\n",
            MAKEFILE + b"test: ; @true\n",
        ):
            with self.subTest(makefile=makefile):
                notes, errors = check(WORKFLOW, makefile, BASE, expected=ISSUE)
                self.assertEqual(notes, [])
                self.assertTrue(errors[0].startswith("FAIL "))

    def test_malformed_skipped_conditional_shadowed_or_undiscoverable_is_not_xfail(self):
        for source in (
            BASE + b"    def broken(:\n",
            BASE + b"return\n",
            BASE + METHOD.replace(b"    def", b"    @unittest.skip('not checked')\n    def"),
            BASE + METHOD.replace(b"    def", b"    async def"),
            BASE + METHOD.replace(b"(self)", b"(self, required)"),
            BASE + METHOD.replace(b"    def", b"    if False:\n        def")
                         .replace(b"        self.", b"            self."),
            BASE + METHOD.replace(b'self.assertIn("setup", "make setup")', b'self.skipTest("skip")'),
            BASE + METHOD + METHOD,
            BASE + METHOD + b"    __unittest_skip__ = True\n",
            BASE + METHOD + b"PublisherTests = None\n",
            BASE + METHOD + b"def load_tests(*args):\n    return None\n",
            BASE.replace(b"unittest.TestCase", b"object"),
            BASE.replace(b"class PublisherTests", b"class RenamedTests"),
            BASE.replace(b"class PublisherTests", b"@unittest.skip('not checked')\nclass PublisherTests"),
        ):
            with self.subTest(source=source):
                notes, errors = check(WORKFLOW, MAKEFILE, source, expected=ISSUE)
                self.assertEqual(notes, [])
                self.assertTrue(errors[0].startswith("FAIL "))

    def test_reads_only_named_regular_blobs_from_exact_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            def git(*args):
                return subprocess.check_output(("git", *args), cwd=repo, text=True).strip()

            git("init", "-q")
            git("config", "user.name", "Test Fixture")
            git("config", "user.email", "tests@example.invalid")
            git("config", "commit.gpgsign", "false")
            tracked = repo / TEST_FILE
            tracked.parent.mkdir()
            tracked.write_bytes(BASE)
            git("add", ".")
            git("commit", "-qm", "Commit fixture")
            first = git("rev-parse", "HEAD")
            tracked.unlink()
            tracked.symlink_to("../elsewhere.py")
            (repo / "elsewhere.py").write_bytes(BASE + METHOD)
            git("add", ".")
            git("commit", "-qm", "Use symlink fixture")
            second = git("rev-parse", "HEAD")

            self.assertEqual(tracked_blob(Pin("press", repo, first), TEST_FILE), BASE)
            with self.assertRaisesRegex(ValueError, "regular tracked blob"):
                tracked_blob(Pin("press", repo, second), TEST_FILE)
            with self.assertRaisesRegex(ValueError, "missing tracked file"):
                tracked_blob(Pin("press", repo, first), "tests/nonexistent.py")


if __name__ == "__main__":
    unittest.main()
