import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from policy import verify_publication


checker_path = Path(os.environ["PROFFER_CHECKER"])
spec = importlib.util.spec_from_file_location("proffer_checker", checker_path)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PublicationTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Reference fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        path = self.root / ".reference/proffer.json"
        path.parent.mkdir()
        self.issue = "https://github.com/example/reference/issues/1"
        handoff = dict(kind="handoff", issue=self.issue, purpose="fixture", producer=["fixture"],
                       requester="fixture", first_step="independently evaluate", artifacts=["example.py"],
                       source=dict(repository="example/reference", base={"none": "fixture"}, work_state="standalone"))
        path.write_text(json.dumps(handoff))
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD")
        self.publication = dict(kind="publication", issue=self.issue, publisher="fixture",
                                handoff=dict(url=f"https://github.com/example/reference/blob/{self.commit}/.reference/proffer.json", commit=self.commit),
                                supplied=dict(kind="commit", id=self.commit),
                                verification=dict(method="commit-identity", result="matched"))

    def verify(self):
        return verify_publication(self.root, "example/reference", self.publication, checker.errors)

    def test_actual_proffer_schema_and_git_object(self):
        self.assertEqual(self.verify()["issue"], self.issue)
        self.assertNotIn("integration", self.verify())

    def test_wrong_issue_is_not_owned_publication(self):
        self.publication["issue"] += "0"
        with self.assertRaisesRegex(ValueError, "owning issue"):
            self.verify()

    def test_matched_attestation_does_not_override_different_tree(self):
        (self.root / "extra").write_text("different")
        self.git("add", ".")
        self.git("commit", "-qm", "different")
        self.publication["supplied"]["id"] = self.git("rev-parse", "HEAD")
        self.publication["verification"]["method"] = "tree-identity"
        with self.assertRaisesRegex(ValueError, "different trees"):
            self.verify()

    def test_same_tree_can_have_different_commits(self):
        self.git("commit", "--allow-empty", "-qm", "same tree")
        self.publication["supplied"]["id"] = self.git("rev-parse", "HEAD")
        self.publication["verification"]["method"] = "tree-identity"
        self.verify()

    def test_schema_rejects_auto_acceptance_field(self):
        self.publication["accepted"] = True
        with self.assertRaises(ValueError):
            self.verify()

    def test_url_must_name_the_verified_commit(self):
        self.publication["handoff"]["url"] = "https://github.com/example/reference/blob/main/.reference/proffer.json"
        with self.assertRaisesRegex(ValueError, "URL"):
            self.verify()
