import json
import tempfile
import unittest
from pathlib import Path

from policy import StateIdentity, require_state_identity, unchanged_open


class ExplicitStateOpenTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "owned-state"
        self.root.mkdir()
        self.state = self.root / "state.json"
        self.state.write_text(json.dumps({"owner": "owner-a", "schema": "v1", "record": "retained"}))
        self.expected = StateIdentity("owner-a", "v1")

    def open_existing(self):
        value = json.loads(self.state.read_text())
        require_state_identity(StateIdentity(value["owner"], value["schema"]), self.expected)
        return value["record"]

    def test_existing_matching_state_opens_without_changes(self):
        self.assertEqual(unchanged_open(self.root, self.open_existing), "retained")

    def test_unknown_schema_refuses_and_preserves_bytes(self):
        self.state.write_text(json.dumps({"owner": "owner-a", "schema": "future", "record": "retained"}))
        before = self.state.read_bytes()
        with self.assertRaisesRegex(ValueError, "unexpected owner or schema"):
            unchanged_open(self.root, self.open_existing)
        self.assertEqual(self.state.read_bytes(), before)

    def test_matching_schema_cannot_replace_owner_identity(self):
        with self.assertRaises(ValueError):
            require_state_identity(StateIdentity("owner-b", "v1"), self.expected)

    def test_implicit_migration_is_detected_even_after_refusal(self):
        def migrate_then_fail():
            self.state.write_text(json.dumps({"owner": "owner-a", "schema": "v2"}))
            raise ValueError("an error after the unwanted migration")

        with self.assertRaisesRegex(AssertionError, "changed"):
            unchanged_open(self.root, migrate_then_fail)

    def test_open_cannot_initialize_a_missing_tree(self):
        missing = self.root / "not-initialized"

        def initialize():
            missing.mkdir()
            (missing / "state").write_bytes(b"silently initialized")

        with self.assertRaisesRegex(AssertionError, "changed"):
            unchanged_open(missing, initialize)

    def test_refused_open_cannot_erase_existing_data(self):
        def erase():
            self.state.unlink()
            raise ValueError("unsupported schema")

        with self.assertRaisesRegex(AssertionError, "changed"):
            unchanged_open(self.root, erase)

    def test_fixture_boundary_does_not_follow_symlink_state(self):
        (self.root / "linked").symlink_to(self.state)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            unchanged_open(self.root, self.open_existing)


if __name__ == "__main__":
    unittest.main()
