import unittest
from policy import DEFAULT, Deviation, check_versions


class ToolProfileTests(unittest.TestCase):
    def test_common_default_does_not_require_unused_tools(self):
        self.assertEqual(check_versions({"python": DEFAULT["python"], "uv": DEFAULT["uv"]}, []), [])

    def test_tools_already_used_follow_common_versions(self):
        self.assertEqual(check_versions(DEFAULT, DEFAULT), [])
        actual = dict(DEFAULT, ruff="0.16.0")
        self.assertEqual(check_versions(actual, actual), ["ruff: expected 0.17.1, found 0.16.0"])

    def test_float_and_wrong_patch_fail(self):
        for version in ["3.12", "3.12.3", "3.12.12\n"]:
            with self.subTest(version=version):
                self.assertTrue(check_versions({"python": version, "uv": DEFAULT["uv"]}, []))

    def test_missing_declared_tool_cannot_be_omitted(self):
        self.assertTrue(check_versions({"python": DEFAULT["python"], "uv": DEFAULT["uv"]}, ["ruff"]))
        self.assertTrue(check_versions({}, []))

    def test_exact_reasoned_deviation(self):
        actual = dict(DEFAULT, mypy="2.3.0")
        exception = Deviation("2.3.0", "Owned plugin rejects the new AST", "https://example.invalid/issue/1", "Plugin supports the new AST")
        self.assertEqual(check_versions(actual, actual, {"mypy": exception}), [])
        actual["mypy"] = "2.2.0"
        self.assertTrue(check_versions(actual, actual, {"mypy": exception}))

    def test_blank_rationale_and_unused_exception_fail(self):
        for exception in [
            Deviation("2.3.0", "", "https://example.invalid/issue/1", "plugin update"),
            Deviation("2.3.0", "plugin ABI", "", "plugin update"),
            Deviation("2.3.0", "plugin ABI", "https://example.invalid/issue/1", ""),
        ]:
            self.assertTrue(check_versions(dict(DEFAULT, mypy="2.3.0"), DEFAULT, {"mypy": exception}))
        exception = Deviation(DEFAULT["mypy"], "old reason", "https://example.invalid/1", "next update")
        self.assertTrue(check_versions(DEFAULT, DEFAULT, {"mypy": exception}))
        floating = Deviation("3.12", "same runtime family", "https://example.invalid/1", "next update")
        self.assertTrue(check_versions(dict(DEFAULT, python="3.12"), DEFAULT, {"python": floating}))

    def test_unknown_tool_and_unselected_observation_fail(self):
        self.assertTrue(check_versions(dict(DEFAULT, ruby="3.4.0"), DEFAULT))
        self.assertTrue(check_versions(DEFAULT, ["ruff"]))


if __name__ == "__main__":
    unittest.main()
