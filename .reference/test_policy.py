import unittest

from policy import script_errors


class ScriptLocationTests(unittest.TestCase):
    def test_canonical_scripts_allow_nested_owners(self):
        paths = ["scripts/validate.py", "scripts/linux/qualify.sh"]
        self.assertEqual([], script_errors(paths, paths))

    def test_equivalent_tools_name_is_reported(self):
        self.assertEqual(["repository tool belongs under scripts/: tools/validate.py"], script_errors(["tools/validate.py"], ["tools/validate.py"]))

    def test_public_commands_and_package_implementation_are_not_reclassified(self):
        paths = ["check.py", "src/product/tool.py", "scripts/validate.py"]
        self.assertEqual([], script_errors(paths, ["scripts/validate.py"]))

    def test_absent_or_duplicate_classification_fails(self):
        self.assertTrue(script_errors([], ["scripts/deleted.py"]))
        with self.assertRaises(ValueError):
            script_errors(["scripts/a.py"], ["scripts/a.py", "scripts/a.py"])

    def test_prefix_lookalikes_and_escaping_paths_fail(self):
        for path in ["scripts-old/a.py", "scripts/../tools/a.py", "/scripts/a.py", "scripts\\a.py", "scripts//a.py"]:
            with self.subTest(path=path):
                self.assertTrue(script_errors([path], [path]))

    def test_exception_is_exact_current_and_explained(self):
        path = "tools/compat.sh"
        self.assertEqual([], script_errors([path], [path], {path: "External build runner requires this exact entry path until its migration."}))
        self.assertTrue(script_errors([path], [path], {path: " "}))
        self.assertTrue(script_errors([path], [path], {"tools/*": "Too broad."}))

    def test_resolved_exception_must_disappear(self):
        self.assertTrue(script_errors(["scripts/compat.sh"], ["scripts/compat.sh"], {"tools/compat.sh": "Old external caller."}))


if __name__ == "__main__":
    unittest.main()
