import unittest

from policy import repository_test_errors


class RepositoryTestLocationTests(unittest.TestCase):
    def test_canonical_namespace_and_nested_groups(self):
        paths = ["tests/repository/test_policy.py", "tests/repository/build/test_wheels.py"]
        self.assertEqual([], repository_test_errors(paths, paths))

    def test_flat_and_unit_policy_tests_are_reported(self):
        for path in ["tests/test_policy.py", "tests/unit/test_dependency_policy.py"]:
            self.assertTrue(repository_test_errors([path], [path]))

    def test_product_tests_keep_their_owner_even_when_policy_is_the_product(self):
        paths = ["tests/test_protocol.py", "packages/policy/tests/test_api.py", "tests/repository/test_ci.py"]
        self.assertEqual([], repository_test_errors(paths, ["tests/repository/test_ci.py"]))

    def test_default_python_collection_spelling_is_required(self):
        for path in ["tests/repository/ci_policy.py", "tests/repository/test_ci.txt", "tests/repository_extra/test_ci.py"]:
            self.assertTrue(repository_test_errors([path], [path]))

    def test_absent_duplicate_and_escape_inputs_fail(self):
        self.assertTrue(repository_test_errors([], ["tests/repository/test_gone.py"]))
        with self.assertRaises(ValueError):
            repository_test_errors(["tests/repository/test_a.py"], ["tests/repository/test_a.py"] * 2)
        for path in ["tests/repository/../test_ci.py", "/tests/repository/test_ci.py", "tests//repository/test_ci.py"]:
            self.assertTrue(repository_test_errors([path], [path]))

    def test_exception_is_exact_current_and_explained(self):
        path = "tests/test_legacy_collector.py"
        self.assertEqual([], repository_test_errors([path], [path], {path: "External collector addresses this exact test ID until a coordinated transition."}))
        self.assertTrue(repository_test_errors([path], [path], {path: ""}))
        self.assertTrue(repository_test_errors([path], [path], {"tests/*": "Too broad."}))

    def test_resolved_exception_must_disappear(self):
        path = "tests/repository/test_ci.py"
        self.assertTrue(repository_test_errors([path], [path], {path: "Already canonical."}))


if __name__ == "__main__":
    unittest.main()
