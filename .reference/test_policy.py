import unittest

from policy import CATALOG, check_workflows

PATH = ".github/workflows/ci.yml"
LOCATION = PATH + "::jobs.test.steps.0"


def workflow(ref):
    return f"jobs:\n  test:\n    steps:\n      - uses: {ref}\n"


class ActionRevisionTests(unittest.TestCase):
    def test_selected_revision_passes(self):
        for action, sha in CATALOG.items():
            self.assertEqual(check_workflows({PATH: workflow(action + "@" + sha)}), [])

    def test_different_immutable_revision_fails(self):
        self.assertTrue(check_workflows({PATH: workflow("actions/checkout@" + "a" * 40)}))

    def test_version_tag_fails(self):
        self.assertTrue(check_workflows({PATH: workflow("actions/checkout@v4")}))

    def test_intentional_moving_policy_and_local_action_untouched(self):
        for value in ("nashspence/all/.github/workflows/policy.yml@main", "./local", "./actions/checkout", "./jdx/mise-action"):
            self.assertEqual(check_workflows({PATH: workflow(value)}), [])

    def test_case_and_dot_aliases_do_not_bypass_catalog(self):
        for action in ("Actions/Checkout", "actions/checkout/."):
            self.assertTrue(check_workflows({PATH: workflow(action + "@" + CATALOG["actions/checkout"])}))

    def test_exact_legacy_runner_exception(self):
        ref = "actions/checkout@" + "a" * 40
        rule = {"observed": ref, "reason": "This isolated legacy runner cannot execute the catalog runtime.",
                "revisit_when": "The runner's runtime is upgraded and its checkout contract passes."}
        self.assertEqual(check_workflows({PATH: workflow(ref)}, {LOCATION: rule}), [])
        self.assertTrue(check_workflows({PATH: workflow(ref[:-1] + "b")}, {LOCATION: rule}))

    def test_stale_exception_fails(self):
        ref = "actions/checkout@" + CATALOG["actions/checkout"]
        self.assertTrue(check_workflows({PATH: workflow(ref)}, {LOCATION:
            {"observed": ref, "reason": "x", "revisit_when": "y"}}))

    def test_unknown_exception_fails(self):
        self.assertTrue(check_workflows({PATH: workflow("./local")}, {LOCATION: {}}))

    def test_reused_step_anchors_are_inventoried(self):
        ref = "actions/checkout@" + CATALOG["actions/checkout"]
        text = f"jobs:\n  one:\n    steps: &shared\n      - uses: {ref}\n  two:\n    steps: *shared\n"
        self.assertEqual(check_workflows({PATH: text}), [])
        self.assertEqual(len(check_workflows({PATH: text.replace(ref, "actions/checkout@v4")})), 2)

    def test_recursive_alias_fails_closed(self):
        self.assertTrue(check_workflows({PATH: "jobs: &jobs {test: *jobs}"}))

    def test_all_workflows_and_duplicate_yaml_are_checked(self):
        good = workflow("actions/checkout@" + CATALOG["actions/checkout"])
        self.assertTrue(check_workflows({PATH: good, ".github/workflows/other.yml": workflow("actions/checkout@v4")}))
        self.assertTrue(check_workflows({PATH: good + "jobs: {}\n"}))


if __name__ == "__main__":
    unittest.main()
