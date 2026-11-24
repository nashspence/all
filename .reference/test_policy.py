import importlib.util
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from policy import loaded_digest


class LoadedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def load(self, name, content):
        path = self.root / name
        path.write_text(content)
        spec = importlib.util.spec_from_file_location("reader", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_hashes_actual_loaded_origin(self):
        content = b"VALUE = 1\n"
        module = self.load("reader.py", content.decode())
        expected = sha256(content).hexdigest()
        self.assertEqual(loaded_digest(module, expected), expected)

    def test_current_checkout_does_not_attest_stale_installed_module(self):
        module = self.load("installed.py", "VALUE = 0\n")
        checkout = self.root / "checkout.py"
        checkout.write_text("VALUE = 1\n")
        with self.assertRaisesRegex(ValueError, "differs"):
            loaded_digest(module, sha256(checkout.read_bytes()).hexdigest())

    def test_relabeling_file_does_not_replace_loader_origin(self):
        module = self.load("installed.py", "VALUE = 0\n")
        module.__file__ = str(self.root / "checkout.py")
        with self.assertRaisesRegex(ValueError, "unambiguous"):
            loaded_digest(module, "0" * 64)

    def test_non_file_loader_requires_owner_adapter(self):
        import sys
        with self.assertRaises(ValueError):
            loaded_digest(sys, "0" * 64)
