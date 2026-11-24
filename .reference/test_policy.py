from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from policy import SourceError, require_current, run


class ExactSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.root / "source.py").write_text("VALUE = 1\n")
        (self.root / ".gitignore").write_text("output/\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def command(self, code="assert True"):
        return [sys.executable, "-c", code]

    def test_clean_command_runs_once_and_ignored_outputs_are_allowed(self):
        code = "from pathlib import Path; p=Path('output'); p.mkdir(); (p/'result').write_text('one')"
        receipt = run(self.root, self.commit, self.command(code))
        require_current(receipt)
        self.assertEqual((self.root / "output/result").read_text(), "one")

    def test_wrong_commit_untracked_and_staged_assertions_cannot_qualify(self):
        with self.assertRaises(SourceError):
            run(self.root, "0" * 40, self.command())
        (self.root / "new_test.py").write_text("assert True\n")
        with self.assertRaises(SourceError):
            run(self.root, self.commit, self.command())
        self.git("add", "new_test.py")
        with self.assertRaises(SourceError):
            run(self.root, self.commit, self.command())

    def test_mutation_during_execution_or_before_reporting_rejects(self):
        code = "from pathlib import Path; Path('source.py').write_text('VALUE = 2\\n')"
        with self.assertRaises(SourceError):
            run(self.root, self.commit, self.command(code))
        self.git("restore", "source.py")
        receipt = run(self.root, self.commit, self.command())
        (self.root / "new_test.py").write_text("assert True\n")
        with self.assertRaises(SourceError):
            require_current(receipt)

    def test_new_commit_and_failed_execution_do_not_reuse_success(self):
        with self.assertRaises(subprocess.CalledProcessError):
            run(self.root, self.commit, self.command("raise SystemExit(7)"))
        receipt = run(self.root, self.commit, self.command())
        self.git("commit", "--allow-empty", "-qm", "later")
        with self.assertRaises(SourceError):
            require_current(receipt)

    def test_index_flags_cannot_hide_executed_source_edits(self):
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                self.git("update-index", "--" + flag, "source.py")
                (self.root / "source.py").write_text("VALUE = 2\n")
                self.assertEqual(self.git("status", "--porcelain"), "")
                with self.assertRaisesRegex(SourceError, "hide source"):
                    run(self.root, self.commit, self.command())
                self.git("update-index", "--no-" + flag, "source.py")
                self.git("restore", "source.py")


if __name__ == "__main__":
    unittest.main()
