import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from make_help import Pin, capture, check, inventory, run_make


HELP = ".DEFAULT_GOAL := help\n.PHONY: help\nhelp:\n\t@printf '%s\\n' 'Run make help for commands.'\n"
MISS = "missing Makefile"


def git(path, *args):
    return subprocess.run(
        ("git", "-C", str(path), *args), capture_output=True, text=True, check=True,
    ).stdout.strip()


def repo(path, name, files):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.email", "tests@example.invalid")
    git(path, "config", "user.name", "Parity tests")
    for name_in_repo, contents in files.items():
        (path / name_in_repo).write_text(contents)
    git(path, "add", ".")
    git(path, "commit", "--allow-empty", "-qm", "Fixture")
    return Pin(name, path, git(path, "rev-parse", "HEAD"))


def passed(directory, args):
    return subprocess.CompletedProcess(args, 0, "Ready for development\n", "")


def failure(stderr, code=2):
    return subprocess.CompletedProcess(("make",), code, "", stderr)


class MakeHelpTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)

    def repo(self, name="project", **files):
        return repo(self.directory / name, name, files)

    @unittest.skipUnless(shutil.which("make"), "requires GNU Make for the fixture")
    def test_runs_both_commands_from_exact_tracked_bytes(self):
        pin = self.repo(Makefile="include rules.mk\n", **{"rules.mk": HELP})
        (pin.path / "Makefile").write_text("BROKEN WORKTREE")
        (pin.path / "rules.mk").unlink()
        (pin.path / "GNUmakefile").write_text("BROKEN UNTRACKED")
        calls = []

        def make(snapshot, args):
            calls.append(args)
            self.assertFalse((snapshot / ".git").exists())
            self.assertFalse((snapshot / "GNUmakefile").exists())
            return subprocess.run(("make", *args), cwd=snapshot, capture_output=True, text=True,
                                  env={"PATH": os.defpath, "LC_ALL": "C"}, timeout=5)

        self.assertEqual(check([pin], make, {}), ([], []))
        self.assertEqual(calls, [(), ("help",)])

    def test_missing_root_makefile_and_stale_exception(self):
        pin = self.repo()
        (pin.path / "Makefile").write_text(HELP)
        with patch("make_help.run_make") as runner:
            self.assertIn("XFAIL", check([pin], runner, {"project": MISS})[0][0])
            self.assertIn("FAIL", check([pin], runner, {})[1][0])
            self.assertIn("stale exception", check([], runner, {"project": MISS})[1][0])
            runner.assert_not_called()

    def test_xpass_and_changed_failure_are_not_hidden(self):
        pin = self.repo(Makefile=HELP)
        self.assertIn("XPASS", check([pin], passed, {"project": MISS})[1][0])

        def wrong(directory, args):
            return failure("different failure")

        notes, errors = check([pin], wrong, {"project": MISS})
        self.assertEqual(notes, [])
        self.assertIn("different failure", errors[0])

    def test_default_must_match_explicit_and_nonempty(self):
        pin = self.repo(Makefile=HELP)

        def different(directory, args):
            return subprocess.CompletedProcess(args, 0, "help" if args else "other", "")

        def empty(directory, args):
            return subprocess.CompletedProcess(args, 0, " \n", "")

        self.assertIn("same guidance", check([pin], different, {})[1][0])
        self.assertIn("must print guidance", check([pin], empty, {})[1][0])

    def test_inventory_rejects_gitlink_at_wrong_commit(self):
        hub = self.repo("all", Makefile=HELP)
        child = repo(hub.path / "repos" / "child", "child", {"Makefile": HELP})
        git(hub.path, "update-index", "--add", "--cacheinfo", f"160000,{child.commit},repos/child")
        git(hub.path, "commit", "-qm", "Pin child")
        self.assertEqual([pin.name for pin in inventory(hub.path)], ["all", "child"])
        git(child.path, "commit", "--allow-empty", "-qm", "Unexpected child checkout")
        with self.assertRaisesRegex(ValueError, "not checked out"):
            list(inventory(hub.path))

    def test_sandbox_infrastructure_failure_is_fatal(self):
        with patch("make_help.capture", return_value=failure("daemon unavailable", code=125)) as execute:
            with self.assertRaisesRegex(ValueError, "Docker could not run GNU Make"):
                run_make("make-help-ci:local", self.directory, ("help",))
        command = execute.call_args.args[0]
        self.assertIn("--network=none", command)
        self.assertIn("--read-only", command)
        self.assertIn("--pull=never", command)
        self.assertIn("--cap-drop=ALL", command)
        self.assertEqual(command[-3:], ("--entrypoint=make", "make-help-ci:local", "help"))

    def test_child_output_and_execution_are_bounded(self):
        result = capture((sys.executable, "-c", "import sys; print('yes'); print('err', file=sys.stderr)"))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "yes\n", "err\n"))
        with self.assertRaisesRegex(ValueError, "output limit"):
            capture((sys.executable, "-c", "print('a' * 8192)"), limit=4096)
        with self.assertRaisesRegex(ValueError, "timed out"):
            capture((sys.executable, "-c", "import time; time.sleep(5)"), timeout=0.2)


if __name__ == "__main__":
    unittest.main()
