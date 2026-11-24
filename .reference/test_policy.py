import unittest

from policy import check_config, render


class EditorTests(unittest.TestCase):
    def test_common_profile(self):
        self.assertEqual(check_config(render(), []), [])

    def test_missing_or_different_default(self):
        for value in [None, "", render().replace("end_of_line = lf", "end_of_line = crlf"), render().replace("indent_size = 4", "indent_size = 2")]:
            self.assertTrue(check_config(value, []))

    def test_markdown_semantics_preserved(self):
        self.assertIn("[*.{md,markdown}]\ntrim_trailing_whitespace = false", render())
        self.assertTrue(check_config(render().replace("trim_trailing_whitespace = false", "trim_trailing_whitespace = true"), []))

    def test_make_tabs_remain(self):
        self.assertIn("[Makefile]\nindent_style = tab", render())
        self.assertTrue(check_config(render().replace("indent_style = tab", "indent_style = space"), []))

    def test_exact_contract_fixture_exception(self):
        exceptions = {"tests/fixtures/exact.txt": {"reason": "Contract fixture requires CRLF and no final newline.", "properties": {"end_of_line": "crlf", "insert_final_newline": "false"}}}
        self.assertEqual(check_config(render(exceptions), ["tests/fixtures/exact.txt"], exceptions), [])
        self.assertTrue(check_config(render(exceptions), [], exceptions))

    def test_no_pattern_wide_or_unreasoned_escape(self):
        for path, reason in [("tests/*", "fixture"), ("../outside", "fixture"), ("x.txt", " ")]:
            exceptions = {path: {"reason": reason, "properties": {"end_of_line": "unset"}}}
            self.assertTrue(check_config(render(exceptions), [path], exceptions))

    def test_no_nested_or_late_shadow(self):
        self.assertTrue(check_config(render(), [], nested_configs=["sub/.editorconfig"]))
        self.assertTrue(check_config(render() + "\n[*.py]\nindent_size=8\n", []))

    def test_duplicates_and_defaults_rejected(self):
        self.assertTrue(check_config(render() + "\n[*]\ncharset=utf-8\n", []))
        self.assertTrue(check_config("[DEFAULT]\ncharset=utf-8\n" + render(), []))

    def test_comments_and_property_case_not_new_conventions(self):
        text = "# comment\n" + render().replace("root = true", "ROOT = TRUE").replace("charset = utf-8", "CHARSET = UTF-8")
        self.assertEqual(check_config(text, []), [])

    def test_exception_values_are_effective_properties(self):
        for properties in [{"end_of_line": "garbage"}, {"charset": "garbage"}, {"indent_size": "0"}, {"insert_final_newline": "sometimes"}]:
            exceptions = {"x.txt": {"reason": "Contract fixture", "properties": properties}}
            self.assertTrue(check_config(render(exceptions), ["x.txt"], exceptions))
        exceptions = {"x.txt": {"reason": "Exact bytes", "properties": {"end_of_line": "unset"}}}
        self.assertEqual(check_config(render(exceptions), ["x.txt"], exceptions), [])

    def test_stale_deviation_is_not_needed(self):
        exceptions = {"x.py": {"reason": "Old workaround", "properties": {"indent_size": "4"}}}
        self.assertTrue(check_config(render(exceptions), ["x.py"], exceptions))


if __name__ == "__main__":
    unittest.main()
