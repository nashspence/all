import pathlib
import subprocess
import tempfile
import unittest

from policy import facade_errors


GOOD = ".DEFAULT_GOAL := help\n.PHONY: help setup test\nhelp:\n\t@printf 'setup test\\n'\nsetup:\n\t@:\ntest: unit\nunit:\n\t@:\n"


class FacadeTests(unittest.TestCase):
    def test_minimum_and_extra_owner_targets(self):
        self.assertEqual([], facade_errors(GOOD + "profile: unit\n"))

    def test_missing_file_and_raw_guidance_are_not_role_targets(self):
        self.assertTrue(facade_errors(None))
        source = ".DEFAULT_GOAL := help\n.PHONY: help\nhelp:\n\t@printf 'python -m unittest\\n'\n"
        self.assertTrue(any("test:" in x for x in facade_errors(source)))

    def test_makefile_names_do_not_shadow_real_files(self):
        self.assertTrue(facade_errors(GOOD.replace("help setup test", "help setup")))

    def test_empty_role_declarations_do_not_pass(self):
        self.assertTrue(facade_errors(GOOD.replace("test: unit", "test:")))

    def test_default_is_literal_single_help_assignment(self):
        for changed in [GOOD.replace(":= help", ":= test"), GOOD.replace(":= help", "?= help"), GOOD + ".DEFAULT_GOAL := test\n"]:
            with self.subTest(changed=changed):
                self.assertTrue(facade_errors(changed))

    def test_continuation_and_recipe_text_cannot_fake_roles(self):
        self.assertEqual([], facade_errors(GOOD.replace("help setup test", "help \\\n setup test")))
        fake = ".DEFAULT_GOAL := help\n.PHONY: help setup test\nhelp:\n\t@echo 'setup: unit'\n\t@echo 'test: unit'\n"
        self.assertTrue(any("setup:" in x for x in facade_errors(fake)))
        with self.assertRaises(ValueError):
            facade_errors(GOOD + "value = \\")

    def test_minimum_example_delegates_failure_and_default_help(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "Makefile").write_text(GOOD.replace("unit:\n\t@:", "unit:\n\t@exit 17"))
            default = subprocess.run(["make", "--no-print-directory"], cwd=root, capture_output=True, text=True)
            explicit = subprocess.run(["make", "--no-print-directory", "help"], cwd=root, capture_output=True, text=True)
            tested = subprocess.run(["make", "--no-print-directory", "test"], cwd=root, capture_output=True, text=True)
            self.assertEqual((0, default.stdout), (explicit.returncode, explicit.stdout))
            self.assertNotEqual(0, tested.returncode)


if __name__ == "__main__":
    unittest.main()
