import unittest

from jsonschema import Draft202012Validator, FormatChecker

from policy import require_formats


class RequiredFormatTests(unittest.TestCase):
    cases = {"owner-token": (("accepted-token",), ("rejected-token",))}
    schema = {"type": "string", "format": "owner-token"}

    def checker(self, predicate):
        checker = FormatChecker(formats=[])
        checker.checks("owner-token")(predicate)
        return checker

    def test_missing_checker_would_silently_accept_without_the_guard(self):
        checker = FormatChecker(formats=[])
        self.assertTrue(Draft202012Validator(self.schema, format_checker=checker).is_valid("rejected-token"))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            require_formats(checker, self.cases)

    def test_asserted_format_reaches_the_actual_schema_validator(self):
        checker = self.checker(lambda value: value == "accepted-token")
        validator = Draft202012Validator(self.schema, format_checker=require_formats(checker, self.cases))
        self.assertTrue(validator.is_valid("accepted-token"))
        self.assertFalse(validator.is_valid("rejected-token"))

    def test_registered_but_inert_checker_is_not_qualified(self):
        with self.assertRaisesRegex(ValueError, "accepts its rejected"):
            require_formats(self.checker(lambda value: True), self.cases)

    def test_registered_but_always_rejecting_checker_is_not_qualified(self):
        with self.assertRaisesRegex(ValueError, "rejects its accepted"):
            require_formats(self.checker(lambda value: False), self.cases)

    def test_both_positive_and_negative_examples_are_required(self):
        checker = self.checker(lambda value: value == "accepted-token")
        for examples in (((), ("rejected-token",)), (("accepted-token",), ())):
            with self.subTest(examples=examples), self.assertRaisesRegex(ValueError, "positive and negative"):
                require_formats(checker, {"owner-token": examples})

    def test_annotation_only_profiles_remain_an_explicit_owner_choice(self):
        checker = require_formats(FormatChecker(formats=[]), {})
        self.assertTrue(Draft202012Validator(self.schema, format_checker=checker).is_valid("rejected-token"))

    def test_empty_iterators_cannot_bypass_required_probe_examples(self):
        with self.assertRaisesRegex(ValueError, "positive and negative"):
            require_formats(self.checker(lambda value: True), {"owner-token": (iter(()), iter(()))})
