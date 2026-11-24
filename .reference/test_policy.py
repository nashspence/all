import unittest

import yaml
from jsonschema import Draft202012Validator

from policy import load_json_scalars


class YamlScalarTests(unittest.TestCase):
    def test_reproduced_legacy_implicit_meanings_are_not_inherited(self):
        source = "enabled: yes\nlabel: on\ncount: 010\nseconds: 1:20\n"
        self.assertEqual(yaml.safe_load(source), {"enabled": True, "label": True, "count": 8, "seconds": 80})
        self.assertEqual(load_json_scalars(source), {"enabled": "yes", "label": "on", "count": "010", "seconds": "1:20"})

    def test_json_booleans_and_numbers_keep_their_declared_meaning(self):
        result = load_json_scalars("yes: true\nno: false\nn: null\ni: -10\nf: 1.5\ne: 1e3\n")
        self.assertEqual(result, {"yes": True, "no": False, "n": None, "i": -10, "f": 1.5, "e": 1000.0})

    def test_quoted_values_and_block_text_remain_strings(self):
        self.assertEqual(load_json_scalars('flag: "true"\nnumber: "010"\nbody: |\n  yes\n  1:20\n'),
                         {"flag": "true", "number": "010", "body": "yes\n1:20\n"})

    def test_nested_dates_hex_underscores_and_yaml_only_floats_are_strings(self):
        result = load_json_scalars("items:\n  - [2026-11-24, 0x10, 1_000, .inf, .nan, True, OFF]\n")
        self.assertEqual(result, {"items": [["2026-11-24", "0x10", "1_000", ".inf", ".nan", "True", "OFF"]]})

    def test_typed_schema_rejects_legacy_literals_instead_of_receiving_changed_numbers(self):
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}
        validator = Draft202012Validator(schema)
        self.assertTrue(validator.is_valid(load_json_scalars("count: 10\n")))
        self.assertFalse(validator.is_valid(load_json_scalars("count: 010\n")))

    def test_structure_is_not_weakened_while_changing_scalar_resolution(self):
        for source in ("a: 1\na: 2\n", "a: &a [*a]\n", "a: !!str 1\n", "a: 1\n---\na: 2\n", "%YAML 1.1\n---\na: 1\n"):
            with self.subTest(source=source), self.assertRaises((ValueError, yaml.YAMLError)):
                load_json_scalars(source)

    def test_overflow_is_rejected_without_a_global_integer_magnitude_limit(self):
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            load_json_scalars("number: 1e999\n")
        self.assertEqual(load_json_scalars("number: 99999999999999999999999999\n"), {"number": 99999999999999999999999999})
