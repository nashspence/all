import unittest

from policy import missing_updates, surfaces, update_routes


def config(*entries):
    return {"version": 2, "updates": [
        {"package-ecosystem": eco, "directory": directory,
         "schedule": {"interval": "weekly"}, "open-pull-requests-limit": 1}
        for eco, directory in entries
    ]}


class UpdateCoverageTests(unittest.TestCase):
    def test_current_manifest_inventory_drives_coverage(self):
        paths = ["uv.lock", ".github/workflows/ci.yml", "package-lock.json", "service/Dockerfile"]
        expected = {("uv", "/"), ("github-actions", "/"), ("npm", "/"), ("docker", "/service")}
        self.assertEqual(surfaces(paths), expected)
        self.assertEqual(missing_updates(paths, config(*expected)), ())

    def test_new_manifest_exposes_missing_update_route(self):
        current = config(("uv", "/"), ("github-actions", "/"))
        self.assertEqual(missing_updates(["uv.lock", ".github/workflows/ci.yml", "web/package-lock.json"], current), (("npm", "/web"),))

    def test_hidden_owned_directory_keeps_its_exact_identity(self):
        self.assertEqual(surfaces([".build-fixtures/Dockerfile"]), {("docker", "/.build-fixtures")})

    def test_missing_config_fails_only_for_discovered_surfaces(self):
        self.assertEqual(missing_updates(["README.md", "minisign.pub"], None), ())
        self.assertEqual(missing_updates([".github/workflows/ci.yml"], None), (("github-actions", "/"),))

    def test_paused_or_other_branch_route_does_not_cover_default(self):
        for field, value in [("open-pull-requests-limit", 0), ("target-branch", "release")]:
            current = config(("uv", "/"))
            current["updates"][0][field] = value
            self.assertEqual(missing_updates(["uv.lock"], current), (("uv", "/"),))

    def test_multiple_exact_directories(self):
        current = config(("docker", "/"))
        current["updates"][0].pop("directory")
        current["updates"][0]["directories"] = ["/service", "/tests"]
        self.assertEqual(missing_updates(["service/Dockerfile", "tests/Dockerfile"], current), ())

    def test_exceptions_are_exact_current_and_reasoned(self):
        key = ("npm", "/web")
        self.assertEqual(missing_updates(["web/package-lock.json"], None, exceptions={key: "owner-maintained external updater"}), ())
        for exceptions in [{key: ""}, {("npm", "/"): "wrong scope"}]:
            with self.assertRaises(ValueError):
                missing_updates(["web/package-lock.json"], None, exceptions=exceptions)

    def test_ambiguous_or_invalid_routes_refuse(self):
        for current in [config(("uv", "/"), ("uv", "/")), config(("uv", "/a/../b")), config(("uv", "/**"))]:
            with self.assertRaises(ValueError):
                update_routes(current, "main")
        current = config(("uv", "/"))
        current["updates"][0]["schedule"] = {}
        with self.assertRaises(ValueError):
            update_routes(current, "main")

    def test_no_global_schedule_or_version_is_imposed(self):
        current = config(("uv", "/"))
        current["updates"][0]["schedule"] = {"interval": "monthly"}
        current["updates"][0]["open-pull-requests-limit"] = 3
        self.assertEqual(missing_updates(["uv.lock"], current), ())
