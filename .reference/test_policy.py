import unittest

from policy import witness


def paged_workload(size, counter, repeated_history=False):
    values = []
    for start in range(0, size, 4):
        counter.charge()  # Every page fetch remains in the total.
        for item in range(start, min(start + 4, size)):
            counter.charge()  # Read the item.
            if item == 1:
                counter.charge()  # A real retried read is not reset or discarded.
            if repeated_history:
                for previous in values:
                    counter.charge()  # Retained-history scans accumulate.
                    assert previous < item
            values.append(item)
    return tuple(values)


class GrowthTests(unittest.TestCase):
    def test_complete_paging_and_retry_work_fits_declared_envelope(self):
        observations = witness(
            [8, 32, 128], paged_workload, lambda n: tuple(range(n)), slope=2, intercept=1
        )
        self.assertEqual([item.work for item in observations], [11, 41, 161])

    def test_linear_page_io_does_not_hide_quadratic_retained_history(self):
        with self.assertRaisesRegex(AssertionError, "work bound exceeded"):
            witness(
                [8, 32, 128],
                lambda n, count: paged_workload(n, count, repeated_history=True),
                lambda n: tuple(range(n)),
                slope=2,
                intercept=1,
            )

    def test_incomplete_result_cannot_pass_by_doing_less_work(self):
        with self.assertRaisesRegex(AssertionError, "incomplete result"):
            witness([8, 32], lambda n, count: (), lambda n: tuple(range(n)), slope=2)

    def test_correct_results_without_work_instrumentation_are_not_a_witness(self):
        with self.assertRaisesRegex(ValueError, "observations are missing"):
            witness([8, 32], lambda n, count: tuple(range(n)), lambda n: tuple(range(n)), slope=2)

    def test_extent_and_envelope_are_real_nonnegative_integer_units(self):
        for extents, slope in [([8, 8], 2), ([8, 4], 2), ([True, 8], 2), ([4, 8], True)]:
            with self.subTest(extents=extents, slope=slope), self.assertRaises(ValueError):
                witness(extents, paged_workload, lambda n: tuple(range(n)), slope=slope)


if __name__ == "__main__":
    unittest.main()
