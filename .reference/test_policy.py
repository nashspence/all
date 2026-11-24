from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from policy import verify_bound


def family(signature):
    return "ssh" if signature.startswith(b"-----BEGIN SSH SIGNATURE-----") else "other"


class SignerBindingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(shutil.which("ssh-keygen"), "ssh-keygen is required for real signature verification")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("a", "b"):
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "fixture", "-f", str(self.root / name)],
                check=True, capture_output=True,
            )
        self.subject = b"one exact signed subject\n"
        message = self.root / "message"
        message.write_bytes(self.subject)
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(self.root / "a"), "-n", "all-policy-fixture", str(message)],
            check=True, capture_output=True,
        )
        self.signature = (self.root / "message.sig").read_bytes()
        self.key = self.root / "selected.pub"
        self.key.write_bytes((self.root / "a.pub").read_bytes())
        self.key_a = self.key.read_bytes()
        self.key_b = (self.root / "b.pub").read_bytes()

    def real_verify(self, subject, signature, key):
        with tempfile.TemporaryDirectory(dir=self.root) as temporary:
            temporary = Path(temporary)
            (temporary / "allowed").write_bytes(b"fixture " + key.strip() + b"\n")
            (temporary / "signature").write_bytes(signature)
            subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", str(temporary / "allowed"),
                 "-I", "fixture", "-n", "all-policy-fixture", "-s", str(temporary / "signature")],
                input=subject, check=True, capture_output=True,
            )

    def check(self, **kwargs):
        args = dict(expected_family="ssh", trusted_key_sha256={sha256(self.key_a).hexdigest()},
                    identify_family=family, verify=self.real_verify)
        args.update(kwargs)
        return verify_bound(self.subject, self.signature, self.key, **args)

    def test_actual_crypto_and_exact_key_binding(self):
        result = self.check()
        self.assertEqual(result.public_key_sha256, sha256(self.key_a).hexdigest())
        self.assertEqual(result.subject_sha256, sha256(self.subject).hexdigest())

    def test_rotation_during_attempt_uses_one_snapshot(self):
        def rotate_then_verify(subject, signature, key):
            self.key.write_bytes(self.key_b)
            self.real_verify(subject, signature, key)
        result = self.check(verify=rotate_then_verify)
        self.assertEqual(result.public_key_sha256, sha256(self.key_a).hexdigest())
        self.assertEqual(self.key.read_bytes(), self.key_b)
        with self.assertRaisesRegex(ValueError, "outside independent trust"):
            self.check()

    def test_mismatched_key_pair_fails_real_verification(self):
        self.key.write_bytes(self.key_b)
        with self.assertRaises(subprocess.CalledProcessError):
            self.check(trusted_key_sha256={sha256(self.key_b).hexdigest()})

    def test_wrong_signature_family_is_rejected_before_verifier(self):
        def forbidden(*args):
            self.fail("wrong-family verifier dispatched")
        with self.assertRaisesRegex(ValueError, "family"):
            self.check(expected_family="openpgp", verify=forbidden)

    def test_boolean_success_claim_is_not_a_verifier(self):
        with self.assertRaisesRegex(TypeError, "complete or raise"):
            self.check(verify=lambda *args: True)


if __name__ == "__main__":
    unittest.main()
