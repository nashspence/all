import copy
import unittest

from policy import layout_errors

SETUPTOOLS = {"project": {"name": "sample"}, "build-system": {"build-backend": "setuptools.build_meta"}, "tool": {"setuptools": {"packages": {"find": {"where": ["src"]}}}}}
HATCH = {"project": {"name": "sample"}, "build-system": {"build-backend": "hatchling.build"}, "tool": {"hatch": {"build": {"targets": {"wheel": {"packages": ["src/sample"]}}}}}}
SOURCES = {"pyproject.toml", "src/sample/__init__.py", "tests/test_sample.py"}


class SourceLayoutTests(unittest.TestCase):
    def test_existing_backends_share_one_layout(self):
        for metadata in [SETUPTOOLS, HATCH]:
            self.assertEqual([], layout_errors(metadata, SOURCES))

    def test_flat_package_requires_migration(self):
        metadata = copy.deepcopy(SETUPTOOLS)
        metadata["tool"]["setuptools"]["packages"]["find"] = {"include": ["sample*"]}
        self.assertTrue(layout_errors(metadata, {"sample/__init__.py", "pyproject.toml"}))

    def test_declaring_src_without_sources_is_not_enough(self):
        self.assertTrue(layout_errors(SETUPTOOLS, {"pyproject.toml"}))
        self.assertTrue(layout_errors(HATCH, {"src/other/__init__.py"}))
        self.assertTrue(layout_errors(HATCH, {"src/sample/README.md", "src/other/__init__.py"}))

    def test_extra_search_roots_and_overrides_cannot_escape(self):
        metadata = copy.deepcopy(SETUPTOOLS)
        metadata["tool"]["setuptools"]["packages"]["find"]["where"].append(".")
        self.assertTrue(layout_errors(metadata, SOURCES))
        metadata = copy.deepcopy(SETUPTOOLS)
        metadata["tool"]["setuptools"]["package-dir"] = {"sample": "lib/sample"}
        self.assertTrue(layout_errors(metadata, SOURCES))

    def test_namespace_paths_and_multiple_packages_are_allowed(self):
        metadata = copy.deepcopy(HATCH)
        metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = ["src/ns/one", "src/ns/two"]
        self.assertEqual([], layout_errors(metadata, {"src/ns/one/a.py", "src/ns/two/b.pyi"}))

    def test_flat_shadow_and_path_escape_fail(self):
        self.assertTrue(layout_errors(SETUPTOOLS, SOURCES | {"sample/old.py"}))
        with self.assertRaises(ValueError):
            layout_errors(SETUPTOOLS, SOURCES | {"src/../sample.py"})
        metadata = copy.deepcopy(HATCH)
        metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = ["src/../sample"]
        self.assertTrue(layout_errors(metadata, SOURCES))

    def test_virtual_workspaces_do_not_need_a_fake_package(self):
        self.assertEqual([], layout_errors({"tool": {"uv": {"workspace": {"members": ["packages/*"]}}}}, set()))

    def test_unknown_backends_and_remapping_need_real_adapters(self):
        metadata = copy.deepcopy(HATCH)
        metadata["tool"]["hatch"]["build"]["sources"] = {"lib": ""}
        self.assertTrue(layout_errors(metadata, SOURCES))
        self.assertTrue(layout_errors({"project": {"name": "sample"}}, SOURCES))

    def test_hatch_extra_source_routes_require_an_adapter(self):
        for scope in ["build", "wheel"]:
            for key in ["force-include", "hooks", "only-include", "include"]:
                metadata = copy.deepcopy(HATCH)
                target = metadata["tool"]["hatch"]["build"]
                if scope == "wheel":
                    target = target["targets"]["wheel"]
                target[key] = {"outside.py": "sample/x.py"} if key == "force-include" else ["outside.py"]
                self.assertTrue(layout_errors(metadata, SOURCES | {"outside.py"}))

    def test_unhandled_setuptools_modules_and_explicit_lists_do_not_pass(self):
        metadata = copy.deepcopy(SETUPTOOLS)
        metadata["tool"]["setuptools"]["py-modules"] = ["outside"]
        self.assertTrue(layout_errors(metadata, SOURCES | {"outside.py"}))
        for packages in [[], ["sample"]]:
            metadata = copy.deepcopy(SETUPTOOLS)
            metadata["tool"]["setuptools"]["packages"] = packages
            metadata["tool"]["setuptools"]["package-dir"] = {"": "src"}
            self.assertTrue(layout_errors(metadata, SOURCES))


if __name__ == "__main__":
    unittest.main()
