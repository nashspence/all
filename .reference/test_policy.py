import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from policy import blob_bytes, commit_parents


class LiteralGitTests(unittest.TestCase):
    def git(self, *args, env=None):
        return subprocess.check_output(["git", "-C", str(self.root), *args], env=env or self.env,
                                       stderr=subprocess.DEVNULL, text=True).strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Policy fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", os.devnull)
        self.path = self.root / "accepted.txt"
        self.path.write_bytes(b"accepted\n")
        self.git("add", ".")
        self.git("commit", "-qm", "accepted")
        self.first = self.git("rev-parse", "HEAD")
        self.path.write_bytes(b"changed\n")
        self.git("commit", "-qam", "changed")
        self.second = self.git("rev-parse", "HEAD")
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()

    def test_exact_blob_and_original_immediate_parent(self):
        self.assertEqual(blob_bytes(self.root, self.first, "accepted.txt", maximum_bytes=100), b"accepted\n")
        self.assertEqual(commit_parents(self.root, self.second), (self.first,))

    def test_replace_ref_changes_default_read_but_not_literal_identity(self):
        replacement = self.git("commit-tree", self.git("rev-parse", "HEAD^{tree}"), "-m", "replacement root")
        self.git("replace", self.first, replacement)
        self.assertEqual(self.git("show", self.first + ":accepted.txt"), "changed")
        self.assertEqual(blob_bytes(self.root, self.first, "accepted.txt", maximum_bytes=100), b"accepted\n")
        self.assertEqual(commit_parents(self.root, self.first), ())

    def test_local_graft_does_not_hide_the_original_parent(self):
        grafts = self.root / ".git/info/grafts"
        grafts.write_text(self.second + "\n")
        self.assertEqual(self.git("rev-list", "--parents", "-n", "1", self.second), self.second)
        self.assertEqual(commit_parents(self.root, self.second), (self.first,))

    def test_inherited_graft_file_does_not_select_alternate_ancestry(self):
        grafts = self.root / "local-grafts"
        grafts.write_text(self.second + "\n")
        with patch.dict(os.environ, {"GIT_GRAFT_FILE": str(grafts)}):
            self.assertEqual(commit_parents(self.root, self.second), (self.first,))

    def test_moving_ref_or_noncanonical_path_is_not_an_immutable_input(self):
        for commit, path in (("HEAD", "accepted.txt"), (self.first, "./accepted.txt"), (self.first, "../accepted.txt")):
            with self.subTest(commit=commit, path=path), self.assertRaises(ValueError):
                blob_bytes(self.root, commit, path, maximum_bytes=100)

    def test_owner_byte_budget_is_enforced_without_silent_truncation(self):
        with self.assertRaisesRegex(ValueError, "byte budget"):
            blob_bytes(self.root, self.first, "accepted.txt", maximum_bytes=2)

    def test_tag_object_is_not_implicitly_peeled_into_commit_evidence(self):
        self.git("tag", "-a", "selected", "-m", "annotated tag")
        tag = self.git("rev-parse", "refs/tags/selected")
        with self.assertRaisesRegex(ValueError, "actual commit"):
            commit_parents(self.root, tag)
        with self.assertRaisesRegex(ValueError, "actual commit"):
            blob_bytes(self.root, tag, "accepted.txt", maximum_bytes=100)
