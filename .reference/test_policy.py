from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile

from policy import typing_errors


class InlineTypeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, entries):
        path = self.root / "artifact.whl"
        with warnings.catch_warnings(), zipfile.ZipFile(path, "w") as wheel:
            warnings.simplefilter("ignore", UserWarning)
            for name, data in entries:
                wheel.writestr(name, data)
        return path

    def build(self, exclude_marker):
        source = self.root / "source"
        source.mkdir()
        package = source / "example"
        package.mkdir()
        (package / "__init__.py").write_text("def answer() -> int:\n    return 42\n")
        (package / "py.typed").write_text("")
        (source / "pyproject.toml").write_text('''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
[project]
name = "typing-fixture"
version = "0"
[tool.setuptools.packages.find]
include = ["example"]
[tool.setuptools.package-data]
example = ["py.typed"]
''' + ('[tool.setuptools.exclude-package-data]\nexample = ["py.typed"]\n' if exclude_marker else ''))
        output = self.root / "wheels"
        command = "import setuptools.build_meta; print(setuptools.build_meta.build_wheel(" + repr(str(output)) + "))"
        result = subprocess.run([sys.executable, "-c", command], cwd=source, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return output / result.stdout.strip().splitlines()[-1]

    def test_built_inline_typed_package_publishes_marker(self):
        self.assertEqual(typing_errors(self.build(False), ["example"]), ())

    def test_source_marker_does_not_prove_artifact_contains_it(self):
        wheel = self.build(True)
        self.assertTrue((self.root / "source/example/py.typed").is_file())
        self.assertTrue(typing_errors(wheel, ["example"]))

    def test_sibling_marker_does_not_cover_another_owned_package(self):
        wheel = self.archive([("sibling/py.typed", "")])
        self.assertTrue(typing_errors(wheel, ["example"]))

    def test_namespace_subpackage_owns_its_marker(self):
        wheel = self.archive([("namespace/component/py.typed", "")])
        self.assertEqual(typing_errors(wheel, ["namespace/component"]), ())

    def test_duplicate_or_symbolic_marker_is_not_an_unambiguous_file(self):
        wheel = self.archive([("example/py.typed", ""), ("example/py.typed", "")])
        self.assertTrue(typing_errors(wheel, ["example"]))
        link = zipfile.ZipInfo("example/py.typed")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.assertTrue(typing_errors(self.archive([(link, "elsewhere")]), ["example"]))

    def test_owner_package_paths_are_explicit_and_contained(self):
        wheel = self.archive([])
        for path in ("", ".", "../example", "/example", "./example"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                typing_errors(wheel, [path])
