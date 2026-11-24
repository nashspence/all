import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from policy import assert_prose_boundary


class ProseBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        for name, text in {
            "README.md": "See [development](AGENTS.md).\n",
            "AGENTS.md": "Run the executable contracts.\n",
            "LICENSE.txt": "Fixture legal text.\n",
            "sample.md": '{"heading":"example"}',
        }.items():
            (self.root / name).write_text(text)

    def check(self):
        def consume(path):
            self.assertEqual(json.loads(path.read_bytes()), {"heading": "example"})
        assert_prose_boundary(
            self.root, onboarding={"README.md", "AGENTS.md"},
            legal={"LICENSE.txt"}, fixtures={"sample.md": consume},
        )

    def test_real_fixture_consumer_and_legal_exception(self):
        self.check()

    def test_untracked_manual_is_seen(self):
        (self.root / "manual.rst").write_text("Duplicated behavior")
        with self.assertRaisesRegex(AssertionError, "manual.rst"):
            self.check()

    def test_fixture_exception_requires_executable_validity(self):
        (self.root / "sample.md").write_text("not the supported fixture")
        with self.assertRaises(json.JSONDecodeError):
            self.check()

    def test_classifications_cannot_hide_overlap(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            assert_prose_boundary(self.root, onboarding={"README.md"}, legal={"README.md"})

    def test_ignored_output_does_not_become_maintained_prose(self):
        (self.root / ".gitignore").write_text("generated.txt\n")
        (self.root / "generated.txt").write_text("Generated local output")
        self.check()


if __name__ == "__main__":
    unittest.main()
