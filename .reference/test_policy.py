from pathlib import Path
import tempfile
import unittest
import yaml
from policy import assert_action_pins


class ActionPinsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "local").mkdir()
        (self.root / "local/action.yml").write_text("name: local\n")

    def check(self, jobs, **kwargs):
        (self.root / "ci.yml").write_text(yaml.safe_dump({"jobs": jobs}))
        assert_action_pins(self.root, ["ci.yml"], **kwargs)

    def test_step_job_container_and_local_refs(self):
        self.check({
            "test": {"steps": [
                {"uses": "owner/action@" + "a" * 40},
                {"uses": "docker://image@sha256:" + "b" * 64},
                {"uses": "./local"},
                {"run": "uvx --from git+https://github.com/nashspence/all@main all"},
            ]},
            "reuse": {"uses": "owner/repo/.github/workflows/test.yml@" + "c" * 40},
        })

    def test_floating_refs_fail_in_steps_and_reusable_jobs(self):
        for ref in ("actions/checkout@v4", "owner/action@main"):
            for job in ({"uses": ref}, {"steps": [{"uses": ref}]}):
                with self.subTest(ref=ref, job=job), self.assertRaises(AssertionError):
                    self.check({"test": job})

    def test_container_references_are_outside_the_git_pin_rule(self):
        self.check({"test": {"steps": [{"uses": "docker://image:latest"}]}})

    def test_explicit_owner_exception_does_not_match_neighbors(self):
        reference = "nashspence/all/.github/workflows/policy.yml@main"
        reason = {reference: "Owner intentionally consumes the current first-party policy"}
        self.check({"test": {"uses": reference}}, exceptions=reason)
        with self.assertRaises(AssertionError):
            self.check({"test": {"uses": "other/action@main"}}, exceptions=reason)
        with self.assertRaises(ValueError):
            self.check({"test": {"uses": reference}}, exceptions={reference: ""})

    def test_duplicate_uses_is_rejected_before_evaluation(self):
        (self.root / "ci.yml").write_text("jobs:\n  test:\n    uses: owner/action@" + "a" * 40 + "\n    uses: owner/action@main\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            assert_action_pins(self.root, ["ci.yml"])

    def test_local_symlink_escape_is_rejected(self):
        (self.root / "escape").symlink_to(self.root.parent)
        with self.assertRaises(AssertionError):
            self.check({"test": {"uses": "./escape"}})


if __name__ == "__main__":
    unittest.main()
