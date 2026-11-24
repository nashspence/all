import unittest

from policy import EXPECTED, check_workflow

GOOD = """name: CI
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs: {test: {}}
"""


class SupersessionTests(unittest.TestCase):
    def test_common_scope(self):
        self.assertEqual(check_workflow(GOOD), [])

    def test_missing_concurrency_fails(self):
        self.assertTrue(check_workflow("name: CI\njobs: {test: {}}"))

    def test_other_workflows_must_not_collide(self):
        self.assertTrue(check_workflow(GOOD.replace("ci-${{ github.workflow }}-", "ci-")))

    def test_other_refs_must_not_collide(self):
        self.assertTrue(check_workflow(GOOD.replace("-${{ github.ref }}", "")))

    def test_running_work_is_cancelled(self):
        self.assertTrue(check_workflow(GOOD.replace("cancel-in-progress: true", "cancel-in-progress: false")))

    def test_effectful_work_needs_exact_reasoned_deviation(self):
        text = GOOD.replace("cancel-in-progress: true", "cancel-in-progress: false")
        rule = {"observed": {**EXPECTED, "cancel-in-progress": False},
                "reason": "The owner has an externally committed operation awaiting settlement.",
                "revisit_when": "The owner proves cancellation and settlement are safe."}
        self.assertEqual(check_workflow(text, {"concurrency": rule}), [])

    def test_unexplained_or_stale_deviation_fails(self):
        self.assertTrue(check_workflow(GOOD, {"concurrency":
            {"observed": EXPECTED, "reason": "x", "revisit_when": "y"}}))
        self.assertTrue(check_workflow("jobs: {test: {}}", {"concurrency":
            {"observed": None, "reason": "", "revisit_when": "y"}}))

    def test_quoted_or_numeric_boolean_does_not_pass(self):
        for value in ('"true"', "1"):
            self.assertTrue(check_workflow(GOOD.replace("cancel-in-progress: true", "cancel-in-progress: " + value)))

    def test_unknown_deviation_and_duplicate_key_fail(self):
        self.assertTrue(check_workflow(GOOD, {"other": {}}))
        self.assertTrue(check_workflow(GOOD + "concurrency: {}\n"))


if __name__ == "__main__":
    unittest.main()
