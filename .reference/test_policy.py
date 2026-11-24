from pathlib import Path
import tempfile
import unittest
from policy import assert_issue_owned_work


class WorkTrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "owned.py").write_text("# Current parser consumes one input format.\n")

    def check(self, **kwargs):
        assert_issue_owned_work(self.root, ["owned.py"], **kwargs)

    def test_current_design_reason_is_not_a_backlog(self):
        self.check()

    def test_selected_todo_and_fixme_are_rejected(self):
        for text in ("# TODO: add behavior\n", "# FIXME(owner): repair it\n"):
            (self.root / "owned.py").write_text(text)
            with self.assertRaises(AssertionError):
                self.check()

    def test_unselected_product_data_is_not_scanned(self):
        (self.root / "input.txt").write_text("TODO: exact user text")
        self.check()

    def test_product_literal_requires_an_exact_exception(self):
        line = 'SAMPLE = "TODO: imported source text"'
        (self.root / "owned.py").write_text(line + "\n")
        self.check(allowed_lines={"owned.py": {line}})
        (self.root / "owned.py").write_text(line + "\n# TODO: actual backlog\n")
        with self.assertRaises(AssertionError):
            self.check(allowed_lines={"owned.py": {line}})

    def test_only_owner_selected_history_headings_are_rejected(self):
        (self.root / "owned.py").write_text("# Runtime history\n")
        self.check(history_headings={"Changelog"})
        (self.root / "owned.py").write_text("# Changelog\n")
        with self.assertRaises(AssertionError):
            self.check(history_headings={"Changelog"})

    def test_stale_exception_is_not_a_permanent_bypass(self):
        with self.assertRaisesRegex(AssertionError, "unused"):
            self.check(allowed_lines={"owned.py": {"# TODO: removed"}})


if __name__ == "__main__":
    unittest.main()
