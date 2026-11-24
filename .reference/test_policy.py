import unittest

from jsonschema import Draft202012Validator

from policy import exact_hex, hex_schema


class IdentifierTests(unittest.TestCase):
    def readers(self, widths=(40, 64), prefix=""):
        schema = hex_schema(widths=widths, prefix=prefix)
        Draft202012Validator.check_schema(schema)
        return (
            lambda value: exact_hex(value, widths=widths, prefix=prefix),
            Draft202012Validator(schema).is_valid,
        )

    def test_valid_owner_widths_and_literal_digest_prefix(self):
        for widths, prefix in (((40, 64), ""), ((64,), "sha256:")):
            for reader in self.readers(widths, prefix):
                for width in widths:
                    self.assertTrue(reader(prefix + "a" * width))

    def test_dollar_anchor_alone_accepts_the_reproduced_newline(self):
        legacy = Draft202012Validator({"type": "string", "pattern": "^[a-f0-9]{40}$"})
        candidate = "a" * 40 + "\n"
        self.assertTrue(legacy.is_valid(candidate))
        for reader in self.readers():
            self.assertFalse(reader(candidate))

    def test_whole_value_is_checked_without_trimming_or_normalization(self):
        for widths, prefix in (((40, 64), ""), ((64,), "sha256:")):
            good = prefix + "a" * widths[0]
            bad = (good + "\n", good + "\r\n", " " + good, good + " ",
                   good + "0", good[:-1], good[:-1] + "\n", good[:-1] + "ａ")
            for reader in self.readers(widths, prefix):
                for value in bad:
                    with self.subTest(value=repr(value)):
                        self.assertFalse(reader(value))

    def test_prefix_and_lowercase_hex_are_owner_profile_requirements(self):
        for reader in self.readers((64,), "sha256:"):
            for value in ("a" * 64, "SHA256:" + "a" * 64, "sha256:" + "A" * 64,
                          "sha256:" + "g" * 64, "sha256:" + "a" * 32 + "\n" + "a" * 31):
                self.assertFalse(reader(value))

    def test_non_strings_and_unselected_lengths_are_rejected(self):
        for reader in self.readers():
            for value in (None, 123, True, ["a" * 40], "a" * 41, "a" * 63, "a" * 65):
                self.assertFalse(reader(value))

    def test_adjacent_widths_cannot_mix_one_widths_pattern_with_anothers_length(self):
        readers = self.readers((40, 41))
        for value in ("a" * 40 + "\n", "a" * 41 + "\n"):
            for reader in readers:
                self.assertFalse(reader(value))
        for value in ("a" * 40, "a" * 41):
            for reader in readers:
                self.assertTrue(reader(value))

    def test_profile_configuration_cannot_silently_change_width_semantics(self):
        for widths in ((), (True,), (64.0,), (0,), (40, 40)):
            with self.subTest(widths=widths), self.assertRaises(ValueError):
                hex_schema(widths=widths)
