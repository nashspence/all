import unittest
from policy import command_errors, source_errors


PROJECT = '[dependency-groups]\ndev = ["pytest==9.1.1"]\n'
LOCK = 'version = 1\nrevision = 3\n'


def commands(workspace=False):
    prefix = ["mise", "exec", "--", "uv"]
    options = ["--locked", "--group", "dev"] + (["--all-packages"] if workspace else [])
    return {"setup": prefix + ["sync"] + options, "test": prefix + ["run"] + options + ["--", "python", "-m", "unittest", "discover", "-s", "tests"]}


class EnvironmentShapeTests(unittest.TestCase):
    def test_shared_source_and_command_shape(self):
        self.assertEqual(source_errors(PROJECT, LOCK), [])
        self.assertEqual(command_errors(commands(), workspace=False), [])
        self.assertEqual(command_errors(commands(True), workspace=True), [])

    def test_nonpackage_or_empty_dev_group_does_not_require_publishing(self):
        self.assertEqual(source_errors('[dependency-groups]\ndev=[]\n', LOCK), [])

    def test_missing_and_malformed_authorities_fail(self):
        for project, lock in [(None, LOCK), (PROJECT, None), ('[broken', LOCK), (PROJECT, 'version=true'), (PROJECT, 'version=2')]:
            with self.subTest(project=project, lock=lock):
                self.assertTrue(source_errors(project, lock))

    def test_second_hand_authored_dependency_vocabulary_fails(self):
        self.assertTrue(source_errors(PROJECT, LOCK, ['requirements-dev.txt']))
        self.assertTrue(source_errors(PROJECT + '[tool.uv]\ndev-dependencies=[]\n', LOCK))

    def test_unlocked_frozen_or_no_sync_cannot_substitute(self):
        for substitute in ['--frozen', '--no-sync', '--no-dev']:
            actual = commands()
            actual['test'][5] = substitute
            self.assertTrue(command_errors(actual, workspace=False))

    def test_required_scope_and_real_child_command(self):
        self.assertTrue(command_errors(commands(), workspace=True))
        actual = commands()
        actual['test'] = actual['test'][:9]
        self.assertTrue(command_errors(actual, workspace=False))

    def test_global_or_named_environment_is_not_default(self):
        self.assertTrue(command_errors(commands(), workspace=False, project_environment='/tmp/shared-venv'))
        self.assertTrue(command_errors({}, workspace=False))

    def test_empty_or_nonstring_child_arguments_fail(self):
        for argument in ['', ' ', None, 1]:
            actual = commands()
            actual['test'] = actual['test'][:9] + [argument]
            self.assertTrue(command_errors(actual, workspace=False))
        actual = commands()
        actual['test'].append(None)
        self.assertTrue(command_errors(actual, workspace=False))


if __name__ == '__main__':
    unittest.main()
