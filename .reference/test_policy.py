from pathlib import Path
import tempfile
import unittest

from policy import witness


def recover(authority, observer):
    if authority is None:
        raise PermissionError("verified authority is required")
    restored = authority.read_bytes()
    if observer is not None:
        try:
            observer()
        except OSError:
            pass
    return restored


class OptionalStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.serial = 0

    def authority(self):
        self.serial += 1
        path = self.root / f"archive-{self.serial}"
        path.write_bytes(b"verified archive bytes")
        return path

    def check(self, operation):
        witness(
            operation, authority=self.authority, missing_authority=lambda: None,
            current_observation=b"verified archive bytes", stale_observation=b"old cache bytes",
            expected=b"verified archive bytes", refusal=PermissionError,
        )

    def test_authorized_recovery_survives_absent_stale_and_failed_observers(self):
        self.check(recover)
        self.assertEqual(self.serial, 4)

    def test_stale_cache_cannot_substitute_its_bytes(self):
        def wrong(authority, observer):
            result = recover(authority, None)
            return observer() if observer is not None else result

        with self.assertRaisesRegex(AssertionError, "stale"):
            self.check(wrong)

    def test_optional_failure_cannot_block_verified_recovery(self):
        def wrong(authority, observer):
            result = recover(authority, None)
            if observer is not None:
                observer()
            return result

        with self.assertRaisesRegex(OSError, "unavailable"):
            self.check(wrong)

    def test_optional_success_cannot_replace_missing_mandatory_authority(self):
        def wrong(authority, observer):
            if authority is None and observer is not None:
                return observer()
            return recover(authority, observer)

        with self.assertRaisesRegex(AssertionError, "mandatory authority"):
            self.check(wrong)


if __name__ == "__main__":
    unittest.main()
