import hashlib
import json
import unittest
from unittest.mock import patch

import rfc8785
from policy import canonical_bytes, canonical_sha256, require_canonical


class SharedJCSTests(unittest.TestCase):
    def test_unicode_order_and_preservation(self):
        value = {"\ue000": "e\u0301", "😀": "é", "a": True}
        self.assertEqual(canonical_bytes(value), '{"a":true,"😀":"é","\ue000":"e\u0301"}'.encode())
        self.assertNotEqual(canonical_bytes("é"), canonical_bytes("e\u0301"))

    def test_rfc_number_vectors(self):
        self.assertEqual(canonical_bytes([-0.0, 1.0, 1e20, 1e21, 1e-6, 1e-7, 5e-324, 1.7976931348623157e308]),
                         b'[0,1,100000000000000000000,1e+21,0.000001,1e-7,5e-324,1.7976931348623157e+308]')

    def test_recursion_and_array_order(self):
        value = {"z": [{"b": 1, "a": 2}, False, 1], "a": {}}
        before = json.dumps(value)
        self.assertEqual(canonical_bytes(value), b'{"a":{},"z":[{"a":2,"b":1},false,1]}')
        self.assertEqual(json.dumps(value), before)
        self.assertNotEqual(canonical_bytes([True, 1]), canonical_bytes([1, True]))

    def test_control_escaping(self):
        self.assertEqual(canonical_bytes('\x00\b\t\n\f\r\x1f"\\/'), b'"\\u0000\\b\\t\\n\\f\\r\\u001f\\"\\\\/"')

    def test_exact_integer_domain(self):
        self.assertEqual(canonical_bytes(2**53 - 1), b'9007199254740991')
        self.assertEqual(canonical_bytes("9007199254740993"), b'"9007199254740993"')
        for value in (2**53, -(2**53), 2**63 - 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_bytes(value)
        self.assertEqual(canonical_bytes(float(2**53)), b'9007199254740992')

    def test_invalid_values(self):
        for value in (float("nan"), float("inf"), "\ud800", "\ufdd0", "\U0010ffff", {"\udfff": 1}, {1: "x"}, (1, 2), b"x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_bytes(value)
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(ValueError):
            canonical_bytes(cycle)

    def test_hash_referent_and_canonical_wire(self):
        value = {"b": 2, "a": 1}
        expected = b'{"a":1,"b":2}'
        self.assertEqual(canonical_sha256(value), hashlib.sha256(expected).hexdigest())
        self.assertEqual(require_canonical(expected, json.loads), value)
        for raw in (b'{"b":2,"a":1}', b'{ "a":1,"b":2}', b'{"a":1,"a":1,"b":2}'):
            with self.assertRaises(ValueError):
                require_canonical(raw, json.loads)

    def test_admission_is_not_bypassed(self):
        def refuse(raw):
            raise ValueError("owner admission failed")
        with self.assertRaisesRegex(ValueError, "owner admission failed"):
            require_canonical(b'null', refuse)

    def test_unreviewed_version_fails(self):
        with patch.object(rfc8785, "__version__", "0.2.0"), self.assertRaises(ValueError):
            canonical_bytes(None)


if __name__ == '__main__':
    unittest.main()
