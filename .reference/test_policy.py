from pathlib import Path
import tempfile
import unittest

from policy import discover, require_coverage


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.add_project("packages/core")
        self.add_project("implementations/first")

    def add_project(self, name):
        path = self.root / name
        path.mkdir(parents=True)
        (path / "pyproject.toml").write_text("[project]\nname = 'fixture'\n")

    def projects(self):
        return discover(self.root, ["packages", "implementations"])

    def test_current_collection_covers_each_project(self):
        projects = self.projects()
        require_coverage(projects, {"unit": projects, "compile": projects})

    def test_new_project_reveals_omission_without_an_updated_expected_list(self):
        previous = self.projects()
        self.add_project("implementations/second")
        with self.assertRaisesRegex(ValueError, "second"):
            require_coverage(self.projects(), {"unit": previous, "compile": self.projects()})

    def test_equal_counts_do_not_hide_wrong_membership_or_duplicates(self):
        for members in [
            ["packages/core", "implementations/retired"],
            ["packages/core", "packages/core"],
        ]:
            with self.subTest(members=members), self.assertRaises(ValueError):
                require_coverage(self.projects(), {"unit": members})

    def test_unrelated_metadata_and_empty_gate_maps_cannot_define_coverage(self):
        self.add_project("fixtures/unrelated")
        self.assertNotIn("fixtures/unrelated", self.projects())
        with self.assertRaises(ValueError):
            require_coverage(self.projects(), {})


if __name__ == "__main__":
    unittest.main()
