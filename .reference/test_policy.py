import copy
import unittest

from policy import PROFILE, check_configs, settings_errors


def settings():
    result = {}
    for path, value in PROFILE.items():
        current = result
        parts = path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = copy.deepcopy(value)
    return result


class StyleTests(unittest.TestCase):
    def test_shared_profile(self):
        self.assertEqual(settings_errors(settings()), [])

    def test_compatibility_target_stays_owned(self):
        for target in ["py311", "py312", "py313"]:
            value = settings()
            value["target-version"] = target
            self.assertEqual(settings_errors(value), [])

    def test_every_shared_setting_rejects_drift(self):
        for key in PROFILE:
            value = settings()
            current = value
            parts = key.split(".")
            for part in parts[:-1]:
                current = current[part]
            current[parts[-1]] = None
            with self.subTest(key=key):
                self.assertTrue(any(key in error for error in settings_errors(value)))

    def test_integer_is_not_boolean_or_float(self):
        for altered in [True, 100.0, "100"]:
            value = settings()
            value["line-length"] = altered
            self.assertTrue(settings_errors(value))

    def test_lint_rules_are_a_separate_contract(self):
        value = settings()
        value["lint"] = {"select": ["E", "F"], "mccabe": {"max-complexity": 20}}
        self.assertEqual(settings_errors(value), [])

    def test_exact_reasoned_deviation(self):
        value = settings()
        value["format"]["docstring-code-format"] = True
        deviation = {"format.docstring-code-format": {"value": True, "reason": "Owned executable doctests are qualified in formatted form."}}
        self.assertEqual(settings_errors(value, deviation), [])
        deviation["format.docstring-code-format"]["value"] = False
        self.assertTrue(settings_errors(value, deviation))

    def test_empty_unknown_and_stale_deviations(self):
        self.assertTrue(settings_errors(settings(), {"bad": {"value": 1, "reason": "x"}}))
        self.assertTrue(settings_errors(settings(), {"line-length": {"value": 100, "reason": "old"}}))
        value = settings()
        value["line-length"] = 88
        self.assertTrue(settings_errors(value, {"line-length": {"value": 88, "reason": " "}}))

    def test_no_missing_or_shadow_authority(self):
        self.assertTrue(check_configs({}))
        self.assertTrue(check_configs({"pyproject.toml": "[tool.ruff]\nline-length=100\n", "ruff.toml": "line-length=88\n"}))
        self.assertTrue(check_configs({"package/pyproject.toml": "[tool.ruff]\nline-length=88\n"}))

    def test_malformed_or_inherited_configuration(self):
        self.assertTrue(check_configs({"pyproject.toml": "[tool.ruff]\nline-length=100\nline-length=88\n"}))
        self.assertTrue(check_configs({"pyproject.toml": "tool = true\n"}))
        value = settings()
        value["extend"] = "elsewhere.toml"
        self.assertTrue(settings_errors(value))


if __name__ == "__main__":
    unittest.main()
