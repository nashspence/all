import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from all_policy.__main__ import main
from all_policy.audit import Result
from all_policy.protocol import SOURCE_REPOSITORY


class CliTests(unittest.TestCase):
    def test_performance_cli_rejects_floating_authority_before_running_candidate(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()) as out:
            status = main(["performance", "--authority", directory, "--approved-revision", "main",
                           "--repository", "nashspence/example", "--subject", directory,
                           "--storage", "public-linux-x64-4cpu-native-api-v1=" + directory])
        self.assertEqual(3, status)
        evidence = json.loads(out.getvalue())
        self.assertEqual("failed", evidence["verdict"])
        self.assertIn("full approved commit required", evidence["error"])

    def test_installed_cli_and_module_expose_the_library_check(self):
        root = Path(__file__).resolve().parents[1]
        for command in (["all-policy"], [sys.executable, "-m", "all_policy"]):
            with self.subTest(command=command):
                result = subprocess.run(
                    [*command, "check", str(root), "--repository", SOURCE_REPOSITORY],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr + result.stdout)
                self.assertIn("PASS nashspence/all", result.stdout)

    def test_missing_protocol_is_nonzero(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(1, main(["check", directory]))
            self.assertIn("missing or unreadable", out.getvalue())

    def test_check_uses_github_repository_identity(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": SOURCE_REPOSITORY}):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["check", str(Path(__file__).resolve().parents[1])]))

    def test_audit_reports_every_result_and_fails_if_any_fail(self):
        results = [Result("nashspence/all", ()), Result("nashspence/example", ("missing protocol",))]
        with patch("all_policy.__main__.audit", return_value=results) as audit:
            with patch.dict(os.environ, {"GITHUB_TOKEN": "local", "ALL_REPOS_TOKEN": "owner"}):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(1, main(["audit"]))
                audit.assert_called_once_with("nashspence", token="local", inventory_token="owner")
        self.assertIn("PASS nashspence/all", out.getvalue())
        self.assertIn("FAIL nashspence/example: missing protocol", out.getvalue())

    def test_audit_success_and_empty_inventory_exit_codes(self):
        for results, status in (([Result("nashspence/all", ())], 0), ([], 1)):
            with patch("all_policy.__main__.audit", return_value=results):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(status, main(["audit"]))


if __name__ == "__main__":
    unittest.main()
