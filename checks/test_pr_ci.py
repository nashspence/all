import unittest

from pr_ci import Lane, check, check_workflow


FILE = ".github/workflows/lane.yml"
COMMAND = "python -m pytest -q tests"
LANE = Lane(FILE, "tests", COMMAND)
REPOS = {"project", "keys"}
LANES = {"project": LANE}
EXCLUDED = {"keys"}


def source(event="on: pull_request", step=f"run: {COMMAND}", job="tests"):
    return f"{event}\njobs:\n  {job}:\n    steps:\n      - {step}\n"


class PrCiTests(unittest.TestCase):
    def test_scalar_sequence_mapping_and_ordered_branch_filters(self):
        for event in (
            "on: pull_request",
            "on: [push, pull_request]",
            "'on': {pull_request: null}",
            "on: {pull_request: {types: [opened, reopened, synchronize]}}",
            "on: {pull_request: {branches: [main]}}",
            "on: {pull_request: {branches: ['*', '!m*', 'main']}}",
            "on: {pull_request: {branches-ignore: ['release/**']}}",
        ):
            with self.subTest(event=event):
                check_workflow(source(event), LANE)

    def test_no_normal_pr_or_uncovered_branch_fails(self):
        for event in (
            "on: push",
            "on: {pull_request: {types: [closed]}}",
            "on: {pull_request: {paths: ['src/**']}}",
            "on: {pull_request: {paths-ignore: ['README.md']}}",
            "on: [push, pull_request_target]",
            "on: {pull_request: {branches: [release]}}",
            "on: {pull_request: {branches: ['*', '!main']}}",
            "on: {pull_request: {branches-ignore: [main]}}",
            "on: {pull_request: {branches: [main], branches-ignore: [other]}}",
        ):
            with self.subTest(event=event), self.assertRaises(ValueError):
                check_workflow(source(event), LANE)

    def test_exact_executable_command_in_designated_job(self):
        check_workflow(source(step=f"run: |\n          {COMMAND}"), LANE)
        for step in (
            f"name: {COMMAND}",
            f"run: echo '{COMMAND}'",
            f"run: |\n          # {COMMAND}",
            f"run: |\n          exit 0\n          {COMMAND}",
            f"run: {COMMAND} --collect-only",
            f"run: {COMMAND}\n        if: false",
        ):
            with self.subTest(step=step), self.assertRaises(ValueError):
                check_workflow(source(step=step), LANE)
        with self.assertRaises(ValueError):
            check_workflow(source(job="different"), LANE)

    def test_current_missing_and_unexpected_success_are_distinct(self):
        expected = {("project", LANE): "example/all#99"}
        self.assertEqual(check(REPOS, [], LANES, EXCLUDED, {})[1],
                         [f"FAIL project/{FILE}: designated workflow missing"])
        notes, errors = check(REPOS, [], LANES, EXCLUDED, expected)
        self.assertEqual(errors, [])
        self.assertIn("XFAIL", notes[0])
        notes, errors = check(REPOS, [("project", FILE, source())], LANES, EXCLUDED, expected)
        self.assertEqual(notes, [])
        self.assertIn("XPASS", errors[0])
        notes, errors = check(REPOS, [("project", FILE, source("on: push"))], LANES, EXCLUDED, expected)
        self.assertEqual(notes, [])
        self.assertIn("FAIL", errors[0])

    def test_wrong_path_does_not_count_and_unknown_repo_is_not_silently_excluded(self):
        notes, errors = check(REPOS | {"new-repo"}, [("project", "other.yml", source())],
                              LANES, EXCLUDED, {})
        self.assertEqual(notes, [])
        self.assertEqual(len(errors), 2)
        self.assertIn("new-repo", errors[0])
        self.assertIn(FILE, errors[1])


if __name__ == "__main__":
    unittest.main()
