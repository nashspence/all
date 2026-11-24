import copy
from pathlib import Path
import tempfile
import unittest

import yaml

from all_policy import check_repository, check_workflow
from all_policy.protocol import POLICY_USES, SOURCE_REPOSITORY, WORKFLOW_PATH, WorkflowLoader

CONSUMER_WORKFLOW = """\
name: all
on:
  push: {}
  pull_request: {}
  schedule:
    - cron: '17 3 * * *'
  workflow_dispatch: {}
permissions:
  contents: read
jobs:
  all:
    uses: nashspence/all/.github/workflows/policy.yml@main
"""


class ProtocolTests(unittest.TestCase):
    def test_adoption_is_one_workflow_using_main_as_a_required_test_job(self):
        self.assertEqual((), check_workflow(CONSUMER_WORKFLOW, "nashspence/example"))

    def test_library_checks_the_same_file_as_the_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / WORKFLOW_PATH
            self.assertTrue(check_repository(directory))
            workflow.parent.mkdir(parents=True)
            workflow.write_text(CONSUMER_WORKFLOW)
            self.assertEqual((), check_repository(directory))

    def test_this_repository_obeys_the_protocol_using_its_candidate_policy(self):
        self.assertEqual((), check_repository(Path(__file__).resolve().parents[1], SOURCE_REPOSITORY))
        local = CONSUMER_WORKFLOW.replace(POLICY_USES, "./.github/workflows/policy.yml")
        self.assertEqual((), check_workflow(local, SOURCE_REPOSITORY))
        self.assertTrue(check_workflow(local, "nashspence/example"))

    def test_daily_time_and_display_name_can_vary(self):
        text = CONSUMER_WORKFLOW.replace("name: all", "name: Policy tests").replace("17 3", "59 23")
        self.assertEqual((), check_workflow(text))

    def test_unfiltered_events_can_use_yaml_null(self):
        self.assertEqual((), check_workflow(CONSUMER_WORKFLOW.replace(": {}", ":")))

    def test_filtered_skipped_masked_or_replaced_policy_is_not_adoption(self):
        base = yaml.load(CONSUMER_WORKFLOW, Loader=WorkflowLoader)
        variants = []
        for key, value in (
            ("if", False), ("continue-on-error", True), ("needs", "other"),
            ("with", {"skip": True}), ("secrets", "inherit"),
            ("uses", POLICY_USES.replace("@main", "@v1")),
        ):
            workflow = copy.deepcopy(base)
            workflow["jobs"]["all"][key] = value
            variants.append(workflow)
        for event in ("push", "pull_request"):
            workflow = copy.deepcopy(base)
            workflow["on"][event] = {"paths": ["src/**"]}
            variants.append(workflow)
        for cron in ("* * * * *", "17 3 * * 1", "60 3 * * *", "17 24 * * *"):
            workflow = copy.deepcopy(base)
            workflow["on"]["schedule"] = [{"cron": cron}]
            variants.append(workflow)
        for key in ("schedule", "workflow_dispatch", "pull_request", "push"):
            workflow = copy.deepcopy(base)
            del workflow["on"][key]
            variants.append(workflow)
        for workflow in variants:
            with self.subTest(workflow=workflow):
                self.assertTrue(check_workflow(yaml.safe_dump(workflow)))

    def test_malformed_and_ambiguous_workflows_fail_closed(self):
        for text in ("", "[]", "{", "on: push", "name: all\nname: other",
                     "true: value", "? [a, b]\n: x", "x" * 65537,
                     CONSUMER_WORKFLOW + "jobs: {}\n"):
            with self.subTest(text=text[:80]):
                self.assertTrue(check_workflow(text))


if __name__ == "__main__":
    unittest.main()
