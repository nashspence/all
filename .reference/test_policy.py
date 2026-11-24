import json
from pathlib import Path
import tempfile
import unittest
from policy import assert_example_parity


class ReleaseAuthority:
    def __init__(self, prefix="released/sha256/"):
        self.prefix = prefix

    def projection(self):
        return {"read": [self.prefix], "write": [self.prefix]}

    def permits(self, grants, operation, key):
        return any(key.startswith(prefix) for prefix in grants[operation])


def parse_example(raw):
    value = json.loads(raw)
    if set(value) != {"read", "write"}:
        raise ValueError("invalid role example")
    return {operation: sorted(prefixes) for operation, prefixes in value.items()}


class ExampleParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "role.json"
        self.authority = ReleaseAuthority()
        self.path.write_text('{"write":["released/sha256/"],"read":["released/sha256/"]}')

    def check(self, **kwargs):
        args = dict(parse_example=parse_example, runtime_projection=self.authority.projection)
        args.update(kwargs)
        return assert_example_parity(self.path, **args)

    def test_checked_in_example_and_real_authority_permissions(self):
        grants = self.check()
        self.assertTrue(self.authority.permits(grants, "write", "released/sha256/abc"))
        self.assertFalse(self.authority.permits(grants, "write", "publication-assets/sha256/abc"))

    def test_stale_checked_in_prefix_is_rejected(self):
        self.path.write_text('{"write":["publication-assets/sha256/.released/"],"read":["released/sha256/"]}')
        with self.assertRaisesRegex(AssertionError, "runtime authority"):
            self.check()

    def test_runtime_drift_is_also_rejected(self):
        self.authority.prefix = "new-release-prefix/"
        with self.assertRaises(AssertionError):
            self.check()

    def test_callback_receives_exact_file_bytes(self):
        observed = []
        def inspect(raw):
            observed.append(raw)
            return parse_example(raw)
        self.check(parse_example=inspect)
        self.assertEqual(observed, [self.path.read_bytes()])

    def test_parser_failure_and_nonfinite_projection_are_not_parity(self):
        self.path.write_text('{"unrelated":[]}')
        with self.assertRaises(ValueError):
            self.check()
        self.path.write_text("{}")
        with self.assertRaises(ValueError):
            self.check(parse_example=lambda raw: {"value": float("nan")})

    def test_pass_flags_do_not_establish_semantic_parity(self):
        with self.assertRaisesRegex(TypeError, "passed flags"):
            self.check(parse_example=lambda raw: True, runtime_projection=lambda: True)


if __name__ == "__main__":
    unittest.main()
