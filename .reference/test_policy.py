import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from policy import fixture_environment


class GitFixtureEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("git") is None:
            raise RuntimeError("Git is required for the fixture-isolation proof")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clean = fixture_environment(os.environ)

    def git(self, root, env, *args):
        return subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, text=True)

    def commit_fixture(self, name, env):
        root = self.root / name
        root.mkdir()
        self.git(root, env, "init", "-q", "-b", "main").check_returncode()
        (root / "tracked").write_text("fixture\n")
        self.git(root, env, "add", "tracked").check_returncode()
        return root, self.git(root, env, "commit", "-qm", "fixture")

    def test_global_signing_preference_cannot_change_fixture_commit(self):
        config = self.root / "global.gitconfig"
        original = "[commit]\n gpgsign = true\n[gpg]\n program = /nonexistent/fixture-signer\n"
        config.write_text(original)
        poisoned = self.clean | {"GIT_CONFIG_GLOBAL": str(config)}
        _, unisolated = self.commit_fixture("unisolated", poisoned)
        self.assertNotEqual(unisolated.returncode, 0)
        _, isolated = self.commit_fixture("isolated", fixture_environment(poisoned))
        self.assertEqual(isolated.returncode, 0, isolated.stderr)
        self.assertEqual(config.read_text(), original)

    def test_injected_config_count_is_not_an_isolation_bypass(self):
        poisoned = self.clean | {
            "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "commit.gpgsign", "GIT_CONFIG_VALUE_0": "true",
            "GIT_CONFIG_KEY_1": "gpg.program", "GIT_CONFIG_VALUE_1": "/nonexistent/fixture-signer",
        }
        _, unisolated = self.commit_fixture("unisolated", poisoned)
        self.assertNotEqual(unisolated.returncode, 0)
        _, isolated = self.commit_fixture("isolated", fixture_environment(poisoned))
        self.assertEqual(isolated.returncode, 0, isolated.stderr)

    def test_inherited_hook_path_does_not_execute_in_fixture(self):
        hooks = self.root / "hooks"
        hooks.mkdir()
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 73\n")
        hook.chmod(0o700)
        config = self.root / "global.gitconfig"
        config.write_text(f"[core]\n hooksPath = {hooks.as_posix()}\n")
        poisoned = self.clean | {"GIT_CONFIG_GLOBAL": str(config)}
        _, unisolated = self.commit_fixture("unisolated", poisoned)
        self.assertNotEqual(unisolated.returncode, 0)
        _, isolated = self.commit_fixture("isolated", fixture_environment(poisoned))
        self.assertEqual(isolated.returncode, 0, isolated.stderr)

    def test_routing_environment_does_not_select_another_repository(self):
        outsider, result = self.commit_fixture("outsider", self.clean)
        result.check_returncode()
        intended, result = self.commit_fixture("intended", self.clean)
        result.check_returncode()
        poisoned = self.clean | {"GIT_DIR": str(outsider / ".git"), "GIT_WORK_TREE": str(outsider)}
        self.assertEqual(self.git(intended, poisoned, "rev-parse", "--show-toplevel").stdout.strip(), str(outsider))
        self.assertEqual(self.git(intended, fixture_environment(poisoned), "rev-parse", "--show-toplevel").stdout.strip(), str(intended))

    def test_fixture_identity_is_explicit_and_parent_is_unchanged(self):
        parent = self.clean | {"GIT_AUTHOR_EMAIL": "ambient@example.invalid", "GIT_TRACE": "1", "EXAMPLE_OPTION": "kept"}
        before = dict(parent)
        env = fixture_environment(parent)
        root, result = self.commit_fixture("fixture", env)
        result.check_returncode()
        self.assertEqual(self.git(root, env, "show", "-s", "--format=%ae").stdout.strip(), "fixture@example.invalid")
        self.assertEqual(env["EXAMPLE_OPTION"], "kept")
        self.assertNotIn("GIT_TRACE", env)
        self.assertEqual(parent, before)

    def test_other_git_environment_controls_do_not_leak(self):
        parent = self.clean | {name: "poison" for name in (
            "GIT_CONFIG_PARAMETERS", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_TEMPLATE_DIR", "GIT_SSH_COMMAND", "git_config_count",
        )}
        env = fixture_environment(parent)
        self.assertTrue(set(env).isdisjoint(set(parent) - set(self.clean)))
