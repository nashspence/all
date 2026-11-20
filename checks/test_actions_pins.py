import tempfile
import unittest
from pathlib import Path

import actions_pins as pins


SHA = "0123456789abcdef" * 2 + "01234567"
TEST_EXPECTED = {
    ("proffer", pins.PROFFER_WORKFLOW, "test", "step", ref): "fixture issue"
    for ref in ("actions/checkout@v4", "actions/setup-python@v5")
}


def workflow(*refs, job="test"):
    return ("jobs:\n  " + job + ":\n    steps:\n" + "".join(
        f"      - uses: '{ref}'\n" for ref in refs
    )).encode()


class ActionPinsTests(unittest.TestCase):
    def test_yaml_parsing_and_scope(self):
        source = f"""name: 'uses: quoted text'
jobs:
  reusable:
    uses: example/remote/.github/workflows/workflow.yaml@{SHA}
  local:
    uses: ./.github/workflows/other.yaml
  test:
    steps:
      - run: |
          uses: ignored/not-real@tag
      - uses: "./.github/actions/local"
      - uses: 'docker://busybox:latest'
      - {{ uses: "actions/checkout@{SHA}", with: {{ token: "uses: ignore/me@v3" }} }}
      - uses: example/owner/subdir@{SHA.upper()} # a comment
"""
        count, notes, errors = pins.check([("other", "test.yaml", source)], {})
        self.assertEqual((count, notes, errors), (3, [], []))

    def test_unpinned_job_level_workflow_fails(self):
        source = "jobs: {test: {uses: example/project/.github/workflows/main.yml@main}}"
        count, notes, errors = pins.check([("other", "ci.yml", source)], {})
        self.assertEqual((count, notes, len(errors)), (1, [], 1))
        self.assertIn("(test, reusable workflow)", errors[0])

    def test_step_exception_does_not_apply_at_job_level(self):
        source = "jobs: {test: {uses: actions/checkout@v4}}"
        count, notes, errors = pins.check([("proffer", pins.PROFFER_WORKFLOW, source)], TEST_EXPECTED)
        self.assertEqual((count, notes, len(errors)), (1, [], 3))
        self.assertIn("(test, reusable workflow)", errors[0])
        self.assertTrue(all("XPASS" in error for error in errors[1:]))

    def test_tracked_file_scan_uses_blob_and_not_worktree_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pins.git(root, "init", "-q")
            hub_workflow = root / ".github/workflows/hub.yml"
            hub_workflow.parent.mkdir(parents=True)
            hub_workflow.write_bytes(workflow("example/action@hub-failure"))
            pins.git(root, "add", ".")
            pins.git(root, "-c", "user.name=Fixture", "-c",
                     "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
            child = root / "repos" / "project"
            child.mkdir(parents=True)
            pins.git(child, "init", "-q")
            path = child / ".github/workflows/test.yaml"
            path.parent.mkdir(parents=True)
            path.write_bytes(workflow(f"example/action@{SHA}"))
            pins.git(child, "add", ".")
            pins.git(child, "-c", "user.name=Fixture", "-c",
                     "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
            commit = pins.git(child, "rev-parse", "HEAD").decode().strip()
            pins.git(root, "update-index", "--add", "--cacheinfo", f"160000,{commit},repos/project")
            hub_workflow.write_bytes(workflow(f"example/action@{SHA}"))
            path.write_bytes(workflow("example/action@uncommitted"))
            (path.parent / "untracked.yml").write_bytes(workflow("example/action@untracked"))
            count, notes, errors = pins.check(pins.workflows(root), {})
            self.assertEqual((count, notes, len(errors)), (2, [], 1))
            self.assertIn("FAIL all/.github/workflows/hub.yml", errors[0])

    def test_invalid_remote_refs_fail(self):
        for ref in ("actions/checkout@v4", "a/b@deadbeef", "a/b", "a/b@${{ inputs.ref }}",
                    "a/b@" + SHA + "0", "a/b@" + SHA[:-1]):
            with self.subTest(ref=ref):
                _, _, errors = pins.check([("other", "ci.yml", workflow(ref))], {})
                self.assertEqual(len(errors), 1)
                self.assertIn("expected a 40-character commit SHA", errors[0])

    def test_expected_failures_are_exact_and_unique(self):
        filename = pins.PROFFER_WORKFLOW
        proffer_refs = ("actions/checkout@v4", "actions/setup-python@v5")
        fixture = ("proffer", filename, workflow(*proffer_refs))
        count, notes, errors = pins.check([fixture], TEST_EXPECTED)
        self.assertEqual((count, len(notes), errors), (2, 2, []))
        for extra in [
            ("other", filename, workflow(*proffer_refs)),
            ("proffer", ".github/workflows/other.yml", workflow(*proffer_refs)),
            ("proffer", filename, workflow(*proffer_refs, job="new")),
            fixture,
        ]:
            with self.subTest(extra=extra):
                _, notes, errors = pins.check([fixture, extra], TEST_EXPECTED)
                self.assertEqual((len(notes), len(errors)), (2, 2))

    def test_fixed_changed_or_removed_ref_makes_exception_stale(self):
        for source in (workflow(f"actions/checkout@{SHA}", "actions/setup-python@v5"),
                       workflow("actions/setup-python@v5"),
                       workflow("actions/checkout@v4.2.2", "actions/setup-python@v5")):
            with self.subTest(source=source):
                _, notes, errors = pins.check([("proffer", pins.PROFFER_WORKFLOW, source)], TEST_EXPECTED)
                self.assertEqual(len(notes), 1)
                self.assertIn("XPASS", errors[-1])

    def test_invalid_yaml_and_duplicate_keys_fail_closed(self):
        for source in ("jobs: [", "jobs: {a: {steps: [], steps: []}}",
                       "jobs: {a: {steps: [{uses: {bad: scalar}}]}}",
                       "jobs: {a: {steps: no}}"):
            with self.subTest(source=source):
                _, _, errors = pins.check([("other", "ci.yml", source)], {})
                self.assertEqual(len(errors), 1)
                self.assertIn("FAIL other/ci.yml", errors[0])


if __name__ == "__main__":
    unittest.main()
