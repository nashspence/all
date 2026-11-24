import sys
import unittest

from policy import python_identity, require_runtime_cohort


class RuntimeCohortTests(unittest.TestCase):
    def test_real_children_resolve_to_the_selected_patch_cohort(self):
        resolved = python_identity(sys.executable)
        self.assertEqual(resolved["python.version"], ".".join(map(str, sys.version_info[:3])))
        fragments = {"one": python_identity(sys.executable), "two": python_identity(sys.executable)}
        require_runtime_cohort(resolved, fragments)

    def test_patch_drift_is_not_compatible_merely_because_tests_passed(self):
        selected = {"python.implementation": "cpython", "python.version": "3.13.16"}
        with self.assertRaisesRegex(ValueError, "differs"):
            require_runtime_cohort(selected, {"one": selected, "two": {**selected, "python.version": "3.13.17"}})

    def test_owned_tool_identity_is_compared_without_a_second_solver(self):
        selected = {"python.version": "3.13.16", "uv.version": "0.11.24"}
        require_runtime_cohort(selected, {"one": dict(selected)})
        with self.assertRaises(ValueError):
            require_runtime_cohort(selected, {"one": {**selected, "uv.version": "0.11.25"}})

    def test_missing_identity_field_cannot_be_inferred_from_another_fragment(self):
        selected = {"python.version": "3.13.16", "uv.version": "0.11.24"}
        with self.assertRaises(ValueError):
            require_runtime_cohort(selected, {"one": {"python.version": "3.13.16"}})

    def test_unexpected_identity_field_requires_owner_review(self):
        with self.assertRaises(ValueError):
            require_runtime_cohort({"python.version": "3.13.16"}, {"one": {"python.version": "3.13.16", "mode": "other"}})

    def test_absence_of_fragments_does_not_establish_a_cohort(self):
        with self.assertRaises(ValueError):
            require_runtime_cohort({"python.version": "3.13.16"}, {})

    def test_boolean_is_not_an_interpreter_identity(self):
        with self.assertRaises(ValueError):
            require_runtime_cohort({"python.version": True}, {"one": {"python.version": "True"}})


if __name__ == "__main__":
    unittest.main()
