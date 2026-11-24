import stat
import json
import os
import subprocess
import tempfile
import unittest
import venv
import warnings
import zipfile
from pathlib import Path

from policy import check_wheel_members, probe_installed_modules


class ArtifactIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "example.whl"

    def wheel(self, extra=()):
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr("example/__init__.py", "ANSWER = 42\n")
            archive.writestr("example-1.dist-info/METADATA", "Name: example\nVersion: 1\n")
            for name, content in extra:
                archive.writestr(name, content)

    def test_owned_package_and_metadata_pass(self):
        self.wheel()
        check_wheel_members(self.path, {"example"})

    def test_sibling_implementation_is_rejected(self):
        self.wheel([("sibling/__init__.py", "")])
        with self.assertRaisesRegex(ValueError, "component boundary"):
            check_wheel_members(self.path, {"example"})

    def test_compile_output_cannot_contaminate_a_later_wheel(self):
        for name in ["example/__pycache__/x.cpython-312.pyc", "example/x.pyo"]:
            with self.subTest(name=name):
                self.wheel([(name, b"bytecode")])
                with self.assertRaisesRegex(ValueError, "bytecode"):
                    check_wheel_members(self.path, {"example"})

    def test_unsafe_paths_are_not_owned_by_prefix(self):
        for name in ["example/../sibling.py", "/example/unsafe.py", "example//x.py", "example\\x.py"]:
            with self.subTest(name=name):
                self.wheel([(name, "")])
                with self.assertRaises(ValueError):
                    check_wheel_members(self.path, {"example"})

    def test_zip_symlink_is_not_a_normal_module(self):
        link = zipfile.ZipInfo("example/linked.py")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.wheel([(link, "../../outside.py")])
        with self.assertRaisesRegex(ValueError, "symlink"):
            check_wheel_members(self.path, {"example"})

    def test_duplicate_metadata_member_is_ambiguous(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.wheel([("example-1.dist-info/METADATA", "Name: replacement\n")])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            check_wheel_members(self.path, {"example"})

    def test_declared_module_cannot_be_missing(self):
        self.wheel()
        with self.assertRaisesRegex(ValueError, "missing"):
            check_wheel_members(self.path, {"example"}, {"command.py"})


class InstalledModuleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = self.root / "installed"
        venv.EnvBuilder(with_pip=False).create(self.environment)
        self.python = self.environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        self.site = Path(json.loads(subprocess.check_output(
            [str(self.python), "-I", "-c", "import json,sysconfig;print(json.dumps(sysconfig.get_path('purelib')))"],
            text=True,
        )))

    def test_actual_venv_import_resolves_inside_its_installation(self):
        (self.site / "owned_probe.py").write_text("ANSWER = 42\n")
        result = probe_installed_modules(self.python, self.environment, ["owned_probe"])
        self.assertEqual(Path(result["owned_probe"]), self.site / "owned_probe.py")

    def test_missing_installation_cannot_borrow_the_checkout(self):
        checkout = self.root / "checkout"
        checkout.mkdir()
        (checkout / "owned_probe.py").write_text("ANSWER = 42\n")
        from unittest.mock import patch

        with patch.dict(os.environ, {"PYTHONPATH": str(checkout)}):
            with self.assertRaisesRegex(ValueError, "probe refused"):
                probe_installed_modules(self.python, self.environment, ["owned_probe"])

    def test_site_path_injection_does_not_make_checkout_code_an_installed_artifact(self):
        checkout = self.root / "checkout"
        checkout.mkdir()
        (checkout / "owned_probe.py").write_text("ANSWER = 42\n")
        (self.site / "source-leak.pth").write_text(str(checkout) + "\n")
        with self.assertRaisesRegex(ValueError, "probe refused"):
            probe_installed_modules(self.python, self.environment, ["owned_probe"])

    def test_wrong_virtual_environment_identity_refuses(self):
        with self.assertRaisesRegex(ValueError, "probe refused"):
            probe_installed_modules(self.python, self.root, ["owned_probe"])


if __name__ == "__main__":
    unittest.main()
