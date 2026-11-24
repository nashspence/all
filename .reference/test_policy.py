import unittest
from policy import assert_hard_cut


class RetiredForm(ValueError):
    pass


def parse(value):
    if set(value) != {"current"}:
        raise RetiredForm("only the current spelling is supported")
    return value["current"]


class HardCutTests(unittest.TestCase):
    def check(self, parser=parse, **kwargs):
        args = dict(accepted=[({"current": 3}, 3)], retired=[{"legacy": 3}], rejection=RetiredForm)
        args.update(kwargs)
        assert_hard_cut(parser, **args)

    def test_current_input_and_specific_retired_rejection(self):
        self.check()

    def test_compatibility_alias_is_detected(self):
        def compatible(value):
            return value.get("current", value.get("legacy"))
        with self.assertRaisesRegex(AssertionError, "still accepted"):
            self.check(compatible)

    def test_unrelated_crash_is_not_retirement_evidence(self):
        def crash(value):
            if "legacy" in value:
                raise ZeroDivisionError("implementation bug")
            return value["current"]
        with self.assertRaises(ZeroDivisionError):
            self.check(crash)

    def test_false_return_is_not_explicit_rejection(self):
        def false(value):
            return False if "legacy" in value else value["current"]
        with self.assertRaisesRegex(AssertionError, "still accepted"):
            self.check(false)

    def test_generic_exception_and_empty_examples_refused(self):
        for options in ({"rejection": Exception}, {"accepted": []}, {"retired": []}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.check(**options)

    def test_current_accepted_behavior_is_not_erased(self):
        with self.assertRaisesRegex(AssertionError, "current"):
            self.check(accepted=[({"current": 3}, 4)])


if __name__ == "__main__":
    unittest.main()
