import unittest

from policy import check_independent_matrices

GOOD = """jobs:
  tests:
    strategy:
      fail-fast: false
      matrix: {python: ['3.11', '3.12']}
"""


class MatrixTests(unittest.TestCase):
    def test_independent_evidence_completes(self):
        self.assertEqual(check_independent_matrices(GOOD), [])

    def test_implicit_platform_default_fails(self):
        self.assertTrue(check_independent_matrices(GOOD.replace("      fail-fast: false\n", "")))

    def test_true_fails(self):
        self.assertTrue(check_independent_matrices(GOOD.replace("fail-fast: false", "fail-fast: true")))

    def test_dynamic_matrix_also_declares_behavior(self):
        self.assertEqual(check_independent_matrices(GOOD.replace("{python: ['3.11', '3.12']}", "'${{ fromJSON(needs.plan.outputs.matrix) }}'")), [])

    def test_quoted_or_numeric_false_does_not_pass(self):
        for value in ('"false"', "0"):
            self.assertTrue(check_independent_matrices(GOOD.replace("fail-fast: false", "fail-fast: " + value)))
        self.assertTrue(check_independent_matrices("jobs: {tests: {strategy: []}}"))

    def test_nonmatrix_work_is_not_changed(self):
        self.assertEqual(check_independent_matrices("jobs: {test: {runs-on: ubuntu-24.04}}"), [])

    def test_speculative_search_can_be_exactly_excepted(self):
        text = GOOD.replace("fail-fast: false", "fail-fast: true")
        deviation = {"tests": {"observed": True,
            "reason": "These jobs are alternative speculative executions, not independent assertions.",
            "revisit_when": "The jobs begin to supply independent required evidence."}}
        self.assertEqual(check_independent_matrices(text, deviation), [])

    def test_stale_or_unknown_exception_and_duplicate_key_fail(self):
        self.assertTrue(check_independent_matrices(GOOD, {"tests": {"observed": False, "reason": "x", "revisit_when": "y"}}))
        self.assertTrue(check_independent_matrices(GOOD, {"missing": {}}))
        self.assertTrue(check_independent_matrices(GOOD + "jobs: {}\n"))


if __name__ == "__main__":
    unittest.main()
