import hashlib
import tempfile
import unittest
from pathlib import Path

from policy import check_protected_baseline


class ProtectedBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "schema-v1.fixture"
        self.path.write_bytes(b"accepted owner baseline\n")
        self.baseline = {self.path.name: hashlib.sha256(self.path.read_bytes()).hexdigest()}

    def test_new_revision_does_not_rewrite_the_accepted_baseline(self):
        (self.root / "schema-v2.fixture").write_bytes(b"new owner baseline\n")
        check_protected_baseline(self.root, self.baseline)

    def test_edit_fails(self):
        self.path.write_bytes(b"replacement history\n")
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            check_protected_baseline(self.root, self.baseline)

    def test_removal_fails(self):
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            check_protected_baseline(self.root, self.baseline)

    def test_symlink_substitution_is_not_preservation(self):
        other = self.root / "other.fixture"
        other.write_bytes(self.path.read_bytes())
        self.path.unlink()
        self.path.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "symlink"):
            check_protected_baseline(self.root, self.baseline)

    def test_escaping_baseline_path_fails(self):
        for relative in ["../outside", "/outside", ".", "sub//file", "sub\\file"]:
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                check_protected_baseline(self.root, {relative: "0" * 64})


if __name__ == "__main__":
    unittest.main()
