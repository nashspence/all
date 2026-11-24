from dataclasses import replace
import unittest

from policy import Case, Execution, Plan, require_complete


class CohortTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan("commit-a", "python-3.13.18/linux", ("cursor[first]", "cursor[last]"))
        cases = tuple(Case(name, "run-a", "passed", "passed", "passed") for name in self.plan.cases)
        self.execution = Execution("run-a", self.plan.source, self.plan.profile, self.plan.identity, cases)

    def test_one_complete_execution_matches_independently_collected_plan(self):
        require_complete(self.plan, self.execution)

    def test_partial_parameter_expansion_and_duplicate_success_are_rejected(self):
        first = self.execution.cases[0]
        for cases in [(first,), (first, first)]:
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                require_complete(self.plan, replace(self.execution, cases=cases))

    def test_successful_case_names_from_different_runs_do_not_form_proof(self):
        first, last = self.execution.cases
        mixed = (first, replace(last, execution="run-b"))
        with self.assertRaisesRegex(ValueError, "separate executions"):
            require_complete(self.plan, replace(self.execution, cases=mixed))

    def test_teardown_failure_skips_and_interruption_override_passing_calls(self):
        first, last = self.execution.cases
        for phase, outcome in [("teardown", "failed"), ("setup", "skipped"), ("call", "interrupted")]:
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                cases = (replace(first, **{phase: outcome}), last)
                require_complete(self.plan, replace(self.execution, cases=cases))

    def test_source_runtime_patch_and_changed_plan_remain_strict(self):
        for changes in [
            {"source": "commit-b"}, {"profile": "python-3.13.17/linux"}, {"plan": "old-plan"}
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                require_complete(self.plan, replace(self.execution, **changes))
        changed = replace(self.plan, cases=(*self.plan.cases, "cursor[extra]"))
        with self.assertRaises(ValueError):
            require_complete(changed, self.execution)


if __name__ == "__main__":
    unittest.main()
