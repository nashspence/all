import copy
import unittest

from policy import check_read_only_jobs, load_workflow

WORKFLOW = """
on:
  pull_request:
permissions:
  contents: read
jobs:
  tests:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        with:
          persist-credentials: false
      - run: python -m unittest
  publish:
    permissions:
      contents: write
    steps:
      - run: publish
        env:
          TOKEN: ${{ secrets.PUBLISH_TOKEN }}
"""


class PrCredentialTests(unittest.TestCase):
    def setUp(self):
        self.workflow = load_workflow(WORKFLOW)
        self.classified = {"tests": {"contents": "read"}}
        self.prohibited = frozenset({"PUBLISH_TOKEN"})

    def check(self, workflow=None):
        check_read_only_jobs(self.workflow if workflow is None else workflow, self.classified, self.prohibited)

    def test_explicit_read_only_job_does_not_classify_unrelated_publication(self):
        self.assertIn("on", self.workflow)
        self.check()

    def test_writable_job_override_cannot_borrow_workflow_read_permissions(self):
        self.workflow["jobs"]["tests"]["permissions"] = {"contents": "write"}
        with self.assertRaisesRegex(ValueError, "permissions"):
            self.check()

    def test_missing_explicit_permissions_refuses(self):
        del self.workflow["permissions"]
        with self.assertRaisesRegex(ValueError, "permissions"):
            self.check()

    def test_checkout_must_explicitly_avoid_persisted_credentials(self):
        for value in [None, "true", True, 0]:
            with self.subTest(value=value):
                workflow = copy.deepcopy(self.workflow)
                workflow["jobs"]["tests"]["steps"][0]["with"]["persist-credentials"] = value
                with self.assertRaisesRegex(ValueError, "retains credentials"):
                    self.check(workflow)

    def test_direct_secret_spelling_variants_and_workflow_environment_are_checked(self):
        for expression in ["${{ secrets.PUBLISH_TOKEN }}", "${{ secrets['publish_token'] }}"]:
            with self.subTest(expression=expression):
                workflow = copy.deepcopy(self.workflow)
                workflow["env"] = {"TOKEN": expression}
                with self.assertRaisesRegex(ValueError, "publication credential"):
                    self.check(workflow)

    def test_unknown_inherited_secret_set_refuses(self):
        self.workflow["jobs"]["tests"]["secrets"] = "inherit"
        with self.assertRaisesRegex(ValueError, "unknown secret set"):
            self.check()

    def test_owner_may_declare_additional_required_read_permission(self):
        self.classified["tests"] = {"contents": "read", "actions": "read"}
        self.workflow["jobs"]["tests"]["permissions"] = dict(self.classified["tests"])
        self.check()

    def test_duplicate_permissions_cannot_choose_a_convenient_value(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_workflow("permissions: {contents: write, contents: read}\njobs: {}\n")

    def test_yaml_merge_or_aliases_are_not_silently_flattened(self):
        for text in ["jobs: {tests: {<<: {permissions: {contents: read}}}}", "base: &base {contents: write}\npermissions: *base\njobs: {}"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                load_workflow(text)


if __name__ == "__main__":
    unittest.main()
