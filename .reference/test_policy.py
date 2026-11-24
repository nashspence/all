import unittest

from policy import ValidationBudget, parse_scale


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


class WatchdogTests(unittest.TestCase):
    def test_scale_applies_once_and_elapsed_time_reduces_the_same_budget(self):
        clock = Clock()
        budget = ValidationBudget(5, parse_scale("3"), clock=clock)
        self.assertEqual(budget.remaining(), 15)
        clock.now += 4
        self.assertEqual(budget.remaining(), 11)
        clock.now += 10
        self.assertEqual(budget.remaining(), 1)
        clock.now += 1
        with self.assertRaises(TimeoutError):
            budget.remaining()

    def test_positive_fraction_never_rounds_to_a_disable_timeout_sentinel(self):
        clock = Clock()
        budget = ValidationBudget(0.00001, clock=clock)
        self.assertEqual(budget.remaining_milliseconds(), 1)
        clock.now += 1
        with self.assertRaises(TimeoutError):
            budget.remaining_milliseconds()

    def test_missing_scale_defaults_but_invalid_values_never_silently_fallback(self):
        self.assertEqual(parse_scale(None), 1)
        for value in ["", "0", "-1", "nan", "inf", "1e999", "true", True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_scale(value)
        with self.assertRaises(ValueError):
            ValidationBudget(1e308, 10)

    def test_clock_regression_or_nonfinite_clock_is_not_accepted(self):
        clock = Clock()
        budget = ValidationBudget(10, clock=clock)
        clock.now -= 1
        with self.assertRaises(ValueError):
            budget.remaining()
        with self.assertRaises(ValueError):
            ValidationBudget(10, clock=lambda: float("nan"))


if __name__ == "__main__":
    unittest.main()
