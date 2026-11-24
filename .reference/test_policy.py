from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from policy import assert_fresh_help


class FreshHelpTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(shutil.which("make"), "make is required for the real help qualification")
        self.assertIsNotNone(shutil.which("git"), "git is required for the real checkout fixture")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", self.root], check=True)

    def makefile(self, body):
        (self.root / "Makefile").write_text(body)
        subprocess.run(["git", "-C", self.root, "add", "Makefile"], check=True)

    def check(self):
        return assert_fresh_help(self.root, required_text=["setup", "test"])

    def test_guidance_works_without_project_environment(self):
        self.makefile(".DEFAULT_GOAL := help\n.PHONY: help\nhelp:\n\t@printf 'Run setup, then test\\n'\n")
        self.assertIn("setup", self.check())

    def test_project_tool_prerequisite_fails(self):
        self.makefile(".DEFAULT_GOAL := help\n.PHONY: help\nhelp:\n\t@missing_project_tool help\n")
        with self.assertRaisesRegex(AssertionError, "failed"):
            self.check()

    def test_mutating_help_is_rejected_without_touching_source(self):
        self.makefile(".DEFAULT_GOAL := help\n.PHONY: help\nhelp:\n\t@printf side-effect > generated\n\t@printf 'setup test\\n'\n")
        with self.assertRaisesRegex(AssertionError, "mutated"):
            self.check()
        self.assertFalse((self.root / "generated").exists())

    def test_default_other_target_is_not_help(self):
        self.makefile("build:\n\t@printf 'building\\n'\n.PHONY: help\nhelp:\n\t@printf 'setup test\\n'\n")
        with self.assertRaisesRegex(AssertionError, "same useful guidance"):
            self.check()

    def test_owner_selected_test_guidance_is_required(self):
        self.makefile(".DEFAULT_GOAL := help\n.PHONY: help\nhelp:\n\t@printf 'setup\\n'\n")
        with self.assertRaisesRegex(AssertionError, "missing"):
            self.check()

    def test_absolute_tracked_symlink_cannot_reuse_original_checkout(self):
        self.makefile(".DEFAULT_GOAL := help\n.PHONY: help\nhelp:\n\t@printf 'setup test\\n'\n")
        (self.root / "original").symlink_to(self.root / "Makefile")
        subprocess.run(["git", "-C", self.root, "add", "original"], check=True)
        with self.assertRaisesRegex(ValueError, "disposable checkout"):
            self.check()


if __name__ == "__main__":
    unittest.main()
