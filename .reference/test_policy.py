import unittest

from policy import check_observation
from reproduce import MUTANTS, SAMPLES, run_case


class ValidationCompositionTests(unittest.TestCase):
    def test_fixed_small_witnesses(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample):
                errors, measured, limits = run_case(*sample)
                self.assertEqual(errors, [])
                self.assertEqual(measured, limits)

    def test_unnecessary_work_even_in_oracle_fails_with_correct_evidence(self):
        for mode, metric in MUTANTS.items():
            with self.subTest(mode=mode):
                errors, measured, limits = run_case(*SAMPLES[-1], mode=mode)
                self.assertGreater(measured[metric], limits[metric])
                self.assertTrue(any(e.startswith(metric + ":") for e in errors))
                self.assertTrue(all(e.split(":")[0] in limits for e in errors), errors)

    def test_receipt_inventory_and_values(self):
        ids = ("a", "b")
        expected = [("a", "1"), ("b", "2")]
        self.assertEqual(check_observation(ids, expected, expected[::-1], {"m": 0}, {"m": 0}), [])
        for actual in (expected[:1], [expected[0], expected[0]], [("a", "1"), ("b", "3")],
                       [("a", "1"), ("c", "2")]):
            self.assertIn("incomplete or incorrect scope evidence",
                          check_observation(ids, expected, actual, {"m": 0}, {"m": 0}))
        with self.assertRaises(ValueError):
            check_observation(ids, expected[:1], expected, {"m": 0}, {"m": 0})
        with self.assertRaises(ValueError):
            check_observation(("a", "a"), expected, expected, {"m": 0}, {"m": 0})

    def test_missing_is_not_zero_and_numeric_domains_are_exact(self):
        expected = [("a", "1")]
        self.assertEqual(check_observation(("a",), expected, expected, {}, {"m": 0}),
                         ["missing work observation: m"])
        self.assertEqual(check_observation(("a",), expected, expected, {"m": 0}, {"m": 0}), [])
        for invalid in (-1, True, 1.0):
            with self.assertRaises(ValueError):
                check_observation(("a",), expected, expected, {"m": invalid}, {"m": 0})
            with self.assertRaises(ValueError):
                check_observation(("a",), expected, expected, {"m": 0}, {"m": invalid})


if __name__ == "__main__":
    unittest.main()
