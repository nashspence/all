from pathlib import Path
import subprocess
import tempfile
import unittest

from policy import checkout_errors


class CheckoutByteTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        (self.root / 'input.js').write_bytes(b'const value = 1;\n')
        (self.root / 'README.md').write_bytes(b'example\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'fixture')

    def test_same_commit_does_not_excuse_checkout_byte_drift(self):
        self.assertEqual((), checkout_errors(self.root, 'HEAD', ['input.js']))
        (self.root / 'input.js').write_bytes(b'const value = 1;\r\n')
        self.assertIn('differ', checkout_errors(self.root, 'HEAD', ['input.js'])[0])

    def test_only_owner_declared_fingerprint_inputs_are_checked(self):
        (self.root / 'README.md').write_bytes(b'example\r\n')
        self.assertEqual((), checkout_errors(self.root, 'HEAD', ['input.js']))

    def test_real_autocrlf_checkout_is_detected(self):
        (self.root / 'input.js').unlink()
        self.git('-c', 'core.autocrlf=true', 'checkout', 'HEAD', '--', 'input.js')
        self.assertIn(b'\r\n', (self.root / 'input.js').read_bytes())
        self.assertTrue(checkout_errors(self.root, 'HEAD', ['input.js']))

    def test_targeted_lf_attributes_stabilize_a_real_checkout(self):
        (self.root / '.gitattributes').write_text('input.js text eol=lf\n')
        self.git('add', '.gitattributes')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'scope attributes')
        (self.root / 'input.js').unlink()
        self.git('-c', 'core.autocrlf=true', 'checkout', 'HEAD', '--', 'input.js')
        self.assertEqual((), checkout_errors(self.root, 'HEAD', ['input.js']))

    def test_missing_or_escaping_inputs_are_not_success(self):
        self.assertTrue(checkout_errors(self.root, 'HEAD', ['missing']))
        with self.assertRaises(ValueError):
            checkout_errors(self.root, 'HEAD', ['../outside'])


if __name__ == '__main__':
    unittest.main()
