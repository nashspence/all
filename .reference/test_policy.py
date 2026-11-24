from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from policy import FileClaim, MARKER, claim_empty_directory, create_owned_file, cleanup_owned_files


class OwnedCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / "run-a"
        self.root.mkdir()
        self.token = claim_empty_directory(self.root)

    def test_real_cleanup_preserves_unclaimed_neighbor(self):
        claim = create_owned_file(self.root, self.token, "owned", b"fixture")
        neighbor = self.root / "unclaimed"
        neighbor.write_bytes(b"leave intact")
        self.assertEqual(cleanup_owned_files(self.root, self.token, [claim]), 1)
        self.assertFalse((self.root / "owned").exists())
        self.assertEqual(neighbor.read_bytes(), b"leave intact")

    def test_concurrent_scopes_with_same_basename_stay_separate(self):
        other = self.parent / "run-b"
        other.mkdir()
        token_b = claim_empty_directory(other)
        claim_a = create_owned_file(self.root, self.token, "same", b"a")
        claim_b = create_owned_file(other, token_b, "same", b"b")
        with self.assertRaisesRegex(ValueError, "another run"):
            cleanup_owned_files(self.root, self.token, [claim_b])
        cleanup_owned_files(self.root, self.token, [claim_a])
        self.assertEqual((other / "same").read_bytes(), b"b")
        cleanup_owned_files(other, token_b, [claim_b])

    def test_wrong_token_and_changed_file_refuse_cleanup(self):
        claim = create_owned_file(self.root, self.token, "owned", b"original")
        with self.assertRaisesRegex(ValueError, "token"):
            cleanup_owned_files(self.root, "0" * 64, [claim])
        (self.root / "owned").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            cleanup_owned_files(self.root, self.token, [claim])

    def test_escape_symlink_and_existing_resource_refused(self):
        with self.assertRaises(ValueError):
            create_owned_file(self.root, self.token, "../outside", b"bad")
        (self.root / "link").symlink_to(self.parent)
        with self.assertRaises(ValueError):
            create_owned_file(self.root, self.token, "link/outside", b"bad")
        create_owned_file(self.root, self.token, "existing", b"first")
        with self.assertRaises(FileExistsError):
            create_owned_file(self.root, self.token, "existing", b"replacement")

    def test_entire_cleanup_plan_preflight_precedes_first_delete(self):
        first = create_owned_file(self.root, self.token, "first", b"first")
        second = create_owned_file(self.root, self.token, "second", b"second")
        (self.root / "second").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            cleanup_owned_files(self.root, self.token, [first, second])
        self.assertTrue((self.root / "first").exists())

    def test_normalized_marker_alias_cannot_delete_ownership(self):
        marker = self.root / MARKER
        info = marker.stat()
        claim = FileClaim("./" + MARKER, self.token, info.st_dev, info.st_ino, sha256(marker.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, "resource path"):
            cleanup_owned_files(self.root, self.token, [claim])
        self.assertEqual(marker.read_text(), self.token)

    def test_duplicate_path_alias_is_refused_before_any_unlink(self):
        claim = create_owned_file(self.root, self.token, "owned", b"fixture")
        for second in (claim, replace(claim, relative="./owned")):
            with self.subTest(second=second.relative), self.assertRaises(ValueError):
                cleanup_owned_files(self.root, self.token, [claim, second])
            self.assertEqual((self.root / "owned").read_bytes(), b"fixture")


if __name__ == "__main__":
    unittest.main()
