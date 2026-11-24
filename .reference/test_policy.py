import hashlib
import unittest
from policy import DEFAULT, BuildException, check_profiles


PATH = 'packages/example/pyproject.toml'
HOOK = 'packages/example/hatch_build.py'
HOOK_BYTES = b'owned native build hook\n'
HATCH = {'build-backend': 'hatchling.build', 'requires': ['hatchling>=1.31.0']}


def project(build=DEFAULT):
    return {PATH: {'project': {'name': 'example'}, 'build-system': build}}


def exception(build=HATCH, witnesses=None, reason='Native extension requires owned hook'):
    return BuildException(build, witnesses if witnesses is not None else {HOOK: hashlib.sha256(HOOK_BYTES).hexdigest()}, reason, 'https://example.invalid/issue/1', 'Native build profile has been qualified on the common backend')


class BuildProfileTests(unittest.TestCase):
    def test_common_profile_and_virtual_workspace(self):
        self.assertEqual(check_profiles(project(), {}), [])
        self.assertEqual(check_profiles({'pyproject.toml': {'tool': {'uv': {'workspace': {}}}}}, {}), [])

    def test_pinned_but_different_and_floating_versions_fail(self):
        for requirement in ['setuptools==84.1.0', 'setuptools>=68']:
            self.assertTrue(check_profiles(project(dict(DEFAULT, requires=[requirement])), {}))

    def test_other_backend_extra_requirement_and_local_backend_fail(self):
        for build in [HATCH, dict(DEFAULT, requires=DEFAULT['requires'] + ['wheel']), dict(DEFAULT, **{'backend-path': ['build-tools']})]:
            self.assertTrue(check_profiles(project(build), {}))

    def test_exact_native_exception(self):
        self.assertEqual(check_profiles(project(HATCH), {HOOK: HOOK_BYTES}, {PATH: exception()}), [])

    def test_changed_config_or_hook_cannot_reuse_exception(self):
        self.assertTrue(check_profiles(project(dict(HATCH, requires=['hatchling>=2'])), {HOOK: HOOK_BYTES}, {PATH: exception()}))
        self.assertTrue(check_profiles(project(HATCH), {HOOK: HOOK_BYTES + b'changed'}, {PATH: exception()}))
        self.assertTrue(check_profiles(project(HATCH), {}, {PATH: exception()}))

    def test_blank_reason_missing_witness_and_wildcard_fail(self):
        self.assertTrue(check_profiles(project(HATCH), {HOOK: HOOK_BYTES}, {PATH: exception(reason='')}))
        self.assertTrue(check_profiles(project(HATCH), {}, {PATH: exception(witnesses={})}))
        self.assertTrue(check_profiles(project(HATCH), {HOOK: HOOK_BYTES}, {'packages/*/pyproject.toml': exception()}))

    def test_stale_exception_and_unowned_paths_fail(self):
        self.assertTrue(check_profiles(project(), {HOOK: HOOK_BYTES}, {PATH: exception(build=DEFAULT)}))
        self.assertTrue(check_profiles({'../pyproject.toml': {'project': {}, 'build-system': DEFAULT}}, {}))

    def test_backslashes_are_not_portable_git_paths(self):
        self.assertTrue(check_profiles({'packages\\example/pyproject.toml': {'project': {}, 'build-system': DEFAULT}}, {}))
        bad_hook = 'packages\\example/hatch_build.py'
        bad_witness = {bad_hook: hashlib.sha256(HOOK_BYTES).hexdigest()}
        self.assertTrue(check_profiles(project(HATCH), {bad_hook: HOOK_BYTES}, {PATH: exception(witnesses=bad_witness)}))

    def test_legacy_metadata_does_not_hide_build_backend(self):
        self.assertTrue(check_profiles({PATH: {"build-system": HATCH}}, {}))
        self.assertEqual(check_profiles({PATH: {"build-system": DEFAULT}}, {}), [])


if __name__ == '__main__':
    unittest.main()
