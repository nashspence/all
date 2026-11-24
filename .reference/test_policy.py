import hashlib
import tempfile
import unittest
from pathlib import Path

from policy import Artifact, Pin, require_locked_subset


class LockedDependencyTests(unittest.TestCase):
    def setUp(self):
        self.digest = hashlib.sha256(b"reviewed wheel bytes").hexdigest()
        self.pin = Pin("Example_Dep", "1.2.3", frozenset({self.digest}))

    def test_selected_artifact_bytes_match_the_owned_pin(self):
        with tempfile.TemporaryDirectory() as temporary:
            wheel = Path(temporary) / "dependency.whl"
            wheel.write_bytes(b"reviewed wheel bytes")
            selected = Artifact("example-dep", "1.2.3", hashlib.sha256(wheel.read_bytes()).hexdigest())
            require_locked_subset([self.pin], [selected])
            wheel.write_bytes(b"unreviewed replacement")
            changed = Artifact("example-dep", "1.2.3", hashlib.sha256(wheel.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, "differs"):
                require_locked_subset([self.pin], [changed])

    def test_version_drift_cannot_borrow_an_approved_hash(self):
        with self.assertRaises(ValueError):
            require_locked_subset([self.pin], [Artifact("example-dep", "1.2.4", self.digest)])

    def test_required_dependency_is_not_optional(self):
        with self.assertRaisesRegex(ValueError, "not resolved"):
            require_locked_subset([self.pin], [])

    def test_case_and_separator_aliases_cannot_duplicate_a_pin(self):
        with self.assertRaisesRegex(ValueError, "duplicate normalized required"):
            require_locked_subset([self.pin, Pin("example.dep", "1.2.3", frozenset({self.digest}))], [])

    def test_two_selected_artifacts_cannot_hide_ambiguity(self):
        artifact = Artifact("example-dep", "1.2.3", self.digest)
        with self.assertRaisesRegex(ValueError, "duplicate normalized selected"):
            require_locked_subset([self.pin], [artifact, artifact])

    def test_subset_scope_does_not_invent_a_second_lock(self):
        require_locked_subset(
            [self.pin],
            [Artifact("example-dep", "1.2.3", self.digest), Artifact("outside-scope", "2", "")],
        )

    def test_pin_requires_nonempty_approved_hashes(self):
        with self.assertRaises(ValueError):
            require_locked_subset([Pin("example-dep", "1.2.3", frozenset())], [])


if __name__ == "__main__":
    unittest.main()
