import unittest
import yaml

from policy import check_updates, profile, route_key


def config(change=None):
    route = {"package-ecosystem": "uv", "directory": "/", **profile("nashspence")}
    if change:
        route.update(change)
    return yaml.safe_dump({"version": 2, "updates": [route]}, sort_keys=False)


class UpdateProfileTests(unittest.TestCase):
    def test_shared_profile_passes(self):
        self.assertEqual(check_updates(config()), [])

    def test_schedule_variation_fails(self):
        self.assertTrue(check_updates(config({"schedule": {"interval": "daily"}})))

    def test_quoted_or_boolean_queue_limit_does_not_pass(self):
        for value in ("1", True):
            self.assertTrue(check_updates(config({"open-pull-requests-limit": value})))

    def test_review_queue_limit_is_explicit(self):
        self.assertTrue(check_updates(config({"open-pull-requests-limit": "5"})))

    def test_security_and_version_groups_remain_distinct(self):
        self.assertTrue(check_updates(config({"groups": {"all": {"patterns": ["*"]}}})))

    def test_assignment_and_commit_prefix_are_predictable(self):
        self.assertTrue(check_updates(config({"assignees": None})))
        self.assertTrue(check_updates(config({"commit-message": {"prefix": "build"}})))

    def test_eligibility_and_versions_are_outside_profile(self):
        self.assertEqual(check_updates(config({"ignore": [{"dependency-name": "python", "versions": [">= 3.13"]}]})), [])

    def test_exact_release_window_exception(self):
        observed = {**profile("nashspence"), "schedule": {"interval": "monthly"}}
        rule = {"observed": observed, "reason": "This release branch admits updates only in its qualification window.",
                "revisit_when": "The release window restriction is removed."}
        self.assertEqual(check_updates(config({"schedule": observed["schedule"]}), deviations={'["uv",["/"],"<default>"]': rule}), [])

    def test_stale_and_unknown_exceptions_fail(self):
        rule = {"observed": profile("nashspence"), "reason": "x", "revisit_when": "y"}
        self.assertTrue(check_updates(config(), deviations={'["uv",["/"],"<default>"]': rule}))
        self.assertTrue(check_updates(config(), deviations={"missing": rule}))

    def test_duplicate_routes_and_ambiguous_yaml_fail(self):
        self.assertNotEqual(
            route_key({"package-ecosystem": "uv", "directories": ["/a", "/b"]}),
            route_key({"package-ecosystem": "uv", "directory": "/a,/b"}))
        doc = yaml.safe_load(config())
        doc["updates"] *= 2
        self.assertTrue(check_updates(yaml.safe_dump(doc)))
        self.assertTrue(check_updates(config() + "updates: []\n"))


if __name__ == "__main__":
    unittest.main()
