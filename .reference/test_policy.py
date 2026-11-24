import unittest

from policy import PATH, check_workflows

GOOD = """name: CI
on:
  push:
    branches: [main]
  pull_request: {}
  workflow_dispatch: {}
jobs:
  verify:
    runs-on: ubuntu-24.04
    steps:
      - run: make test
"""


class EntryPointTests(unittest.TestCase):
    def test_common_doorway(self):
        self.assertEqual(check_workflows({PATH: GOOD}), [])

    def test_release_and_audit_keep_independent_names(self):
        files = {PATH: GOOD, ".github/workflows/audit.yml":
                 "name: audit\non: workflow_dispatch\njobs: {audit: {}}"}
        self.assertEqual(check_workflows(files), [])

    def test_filename_is_predictable(self):
        self.assertTrue(check_workflows({".github/workflows/test.yml": GOOD}))

    def test_name_is_predictable(self):
        self.assertTrue(check_workflows({PATH: GOOD.replace("name: CI", "name: Contract")}))

    def test_manual_entry_is_present(self):
        self.assertTrue(check_workflows({PATH: GOOD.replace("  workflow_dispatch: {}\n", "")}))

    def test_push_and_pr_remain_present(self):
        for event in ("pull_request", "push"):
            value = GOOD.replace("  pull_request: {}\n", "") if event == "pull_request" else GOOD.replace("  push:\n    branches: [main]\n", "")
            self.assertTrue(check_workflows({PATH: value}))

    def test_duplicate_primary_name_rejected(self):
        self.assertTrue(check_workflows({PATH: GOOD, ".github/workflows/old.yml": GOOD}))

    def test_ambiguous_yaml_and_empty_jobs_rejected(self):
        self.assertTrue(check_workflows({PATH: GOOD + "name: CI\n"}))
        self.assertTrue(check_workflows({PATH: "name: CI\non: [push, pull_request, workflow_dispatch]\njobs: {}"}))


if __name__ == "__main__":
    unittest.main()
