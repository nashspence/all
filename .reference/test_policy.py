from pathlib import Path
import tempfile
import unittest
from policy import assert_onboarding_links


class OnboardingLinksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tests").mkdir()
        (self.root / "tests/test_contract.py").write_text("def test_contract():\n    assert True\n")
        (self.root / "AGENTS.md").write_text("# Setup\n# Setup\n# Café\n<a id='explicit'></a>\n")

    def check(self, text):
        (self.root / "README.md").write_text(text)
        assert_onboarding_links(self.root, ["README.md"])

    def test_local_files_headings_references_and_external_links(self):
        self.check(
            "[contract](tests/test_contract.py#L1-L2)\n"
            "[setup](AGENTS.md#setup-1)\n[café](AGENTS.md#caf%C3%A9)\n"
            "[anchor](AGENTS.md#explicit)\n[remote](https://example.invalid/no-check)\n"
            "[setup][development]\n[development]: AGENTS.md#setup\n"
            "[tests](tests/)\n"
        )

    def test_same_file_anchor(self):
        self.check("# Start\n[jump](#start)\n")

    def test_missing_target_and_anchor(self):
        for text in ("[lost](tests/missing.py)", "[lost](AGENTS.md#absent)", "[lost](tests/test_contract.py#L3)"):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                self.check(text)

    def test_escape_and_symlink_escape(self):
        with self.assertRaises(AssertionError):
            self.check("[outside](%2e%2e/outside)")
        (self.root / "escape").symlink_to(self.root.parent)
        with self.assertRaises(AssertionError):
            self.check("[outside](escape/)")

    def test_fenced_examples_are_not_navigation(self):
        self.check("~~~md\n[illustration](missing)\n~~~\n[real](AGENTS.md)\n")

    def test_plain_attribute_example_is_not_an_html_anchor(self):
        (self.root / "AGENTS.md").write_text('The sample value is id="not-an-anchor" in plain text.\n')
        with self.assertRaisesRegex(AssertionError, "missing anchor"):
            self.check("[target](AGENTS.md#not-an-anchor)\n")


if __name__ == "__main__":
    unittest.main()
