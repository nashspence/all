import unittest

from policy import measure


def clock(start, end):
    return iter((start, end)).__next__


class PerformanceTests(unittest.TestCase):
    def test_large_timing_miss_is_successful_and_operation_runs_once(self):
        calls = []

        def transfer(work):
            calls.append("executed")
            work.record(12)
            return b"verified output"

        result, observation = measure(transfer, unit="bytes", goal_seconds=1, clock=clock(0, 10000))
        self.assertEqual(result, b"verified output")
        self.assertEqual(calls, ["executed"])
        self.assertFalse(observation.goal_met)
        self.assertEqual(observation.elapsed_seconds, 10000)

    def test_absent_optional_goal_and_zero_observed_work_are_valid(self):
        _, observation = measure(lambda work: work.record(0), unit="items", clock=clock(0, 0))
        self.assertIsNone(observation.goal_met)
        self.assertIsNone(observation.rate_per_second)

    def test_real_execution_failure_is_not_converted_to_a_timing_outcome(self):
        def failure(work):
            work.record(1)
            raise RuntimeError("operation failed")

        with self.assertRaisesRegex(RuntimeError, "operation failed"):
            measure(failure, unit="items", goal_seconds=10000, clock=clock(0, 1))

    def test_missing_or_invalid_required_measurements_still_fail(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            measure(lambda work: None, unit="items", clock=clock(0, 1))
        for end in [-1, float("nan"), float("inf")]:
            with self.subTest(end=end), self.assertRaises(ValueError):
                measure(lambda work: work.record(1), unit="items", clock=clock(0, end))
        with self.assertRaises(ValueError):
            measure(lambda work: work.record(True), unit="items", clock=clock(0, 1))


if __name__ == "__main__":
    unittest.main()
