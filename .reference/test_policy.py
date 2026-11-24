import unittest

from policy import assert_recovery_budget


def example_adapter(case):
    if case["mandatory"]:
        return "required-work"
    if (not case["replay_safe"] or case["saved"] < 120
            or case["remaining"] <= case["cost"]
            or case["cost"] * 7 > case["saved"]
            or (case["charged"] + case["reserved"] + case["cost"]) * 7 > case["useful"]):
        return "continue"
    return "checkpoint"


class RecoveryBudgetTests(unittest.TestCase):
    def test_common_vectors(self):
        assert_recovery_budget(example_adapter)

    def test_forgetting_reserved_work_fails(self):
        with self.assertRaises(AssertionError):
            assert_recovery_budget(lambda case: example_adapter(case | {"reserved": 0}))

    def test_implicit_total_checkpoint_cap_fails(self):
        with self.assertRaises(AssertionError):
            assert_recovery_budget(lambda case: "continue" if case["attempts"] > 10 else example_adapter(case))

    def test_optional_budget_must_not_suppress_required_work(self):
        with self.assertRaises(AssertionError):
            assert_recovery_budget(lambda case: example_adapter(case | {"mandatory": False}))

    def test_local_benefit_and_shared_cost_are_independent(self):
        for field in ("charged", "cost", "saved", "remaining", "replay_safe"):
            baseline = {"charged": 0, "cost": 20, "saved": 240, "remaining": 500, "replay_safe": True}[field]
            with self.subTest(field=field), self.assertRaises(AssertionError):
                assert_recovery_budget(lambda case: example_adapter(case | {field: baseline}))
