import unittest

from policy import Bound, Case, Scope, check_case, check_matrix
from reproduce import BOUNDS, cases, execute, oracle, report_reader, setup_reader


class ValidationCompositionTests(unittest.TestCase):
    def test_complete_partitioned_work(self):
        self.assertEqual(check_matrix(cases(), execute, oracle, BOUNDS), [])

    def test_whole_report_repeated_read_fails_without_changing_results(self):
        for case in cases():
            self.assertEqual(report_reader(case, lambda *_: None), oracle(case))
        errors = check_matrix(cases(), report_reader, oracle, BOUNDS)
        self.assertTrue(errors)
        self.assertTrue(all("evidence-read-bytes" in e for e in errors))

    def test_repeated_setup_fails_without_changing_results(self):
        for case in cases():
            self.assertEqual(setup_reader(case, lambda *_: None), oracle(case))
        errors = check_matrix(cases(), setup_reader, oracle, BOUNDS)
        self.assertTrue(errors)
        self.assertTrue(all("shared-read-bytes" in e for e in errors))

    def test_legitimately_larger_independent_scope_can_cost_more(self):
        small = Case(b"s", (Scope("a", b"a"), Scope("b", b"b")))
        large = Case(b"s", (Scope("a", b"a" * 100000), Scope("b", b"b")))
        self.assertEqual(check_matrix([small, large], execute, oracle, BOUNDS), [])

    def test_missing_duplicate_and_wrong_receipts_fail(self):
        case = cases()[-1]
        for transform in (lambda r: r[:-1], lambda r: r[:-1] + [r[0]],
                          lambda r: [(n, "wrong") for n, _ in r]):
            with self.subTest(transform=transform):
                errors = check_case(case, lambda c, charge: transform(execute(c, charge)), oracle, BOUNDS)
                self.assertIn("incomplete or incorrect scope evidence", errors)

    def test_missing_meter_is_not_zero_work(self):
        errors = check_case(cases()[0], lambda c, charge: oracle(c), oracle, BOUNDS)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("missing work observation" in e for e in errors))

    def test_explicit_zero_observation_is_valid(self):
        def zero(case, charge):
            charge("reads", 0)
            return oracle(case)
        self.assertEqual(check_case(cases()[0], zero, oracle, {"reads": Bound()}), [])

    def test_invalid_meter_and_bound_values(self):
        for value in (-1, True, 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check_case(cases()[0], lambda c, charge: charge("reads", value), oracle, {"reads": Bound()})
            with self.subTest(bound=value), self.assertRaises(ValueError):
                check_case(cases()[0], execute, oracle, {"reads": Bound(fixed=value)})

    def test_empty_inventories_and_partial_oracle_fail(self):
        for case in (Case(b"", ()), Case(b"", (Scope("a", b""), Scope("a", b"")))):
            with self.assertRaises(ValueError):
                check_case(case, execute, oracle, BOUNDS)
        with self.assertRaises(ValueError):
            check_matrix([], execute, oracle, BOUNDS)
        with self.assertRaises(ValueError):
            check_case(cases()[-1], execute, lambda c: oracle(c)[:-1], BOUNDS)
        with self.assertRaises(ValueError):
            check_case(cases()[0], execute, oracle, {})

    def test_execution_failure_not_converted_into_advisory_timing(self):
        def failure(case, charge):
            raise RuntimeError("real validation failed")
        with self.assertRaisesRegex(RuntimeError, "real validation failed"):
            check_case(cases()[0], failure, oracle, BOUNDS)


if __name__ == "__main__":
    unittest.main()
