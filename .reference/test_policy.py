import unittest

from policy import evidence_output_errors


class EvidenceOutputTests(unittest.TestCase):
    def test_common_root_preserves_owner_and_run_subpaths(self):
        self.assertEqual([], evidence_output_errors({"validation": "artifacts/validation", "profile": "artifacts/profiles/native", "pytest": "artifacts/test-stats"}))

    def test_semantically_similar_build_reports_are_reported(self):
        self.assertTrue(evidence_output_errors({"validation": "build/ci-timing"}))
        self.assertTrue(evidence_output_errors({"profile": ".build/profiles"}))

    def test_same_prefix_is_not_same_root(self):
        self.assertTrue(evidence_output_errors({"validation": "artifacts-old/validation"}))

    def test_invalid_or_escaping_paths_cannot_be_exempted(self):
        for path in ["artifacts/../build/reports", "/artifacts/reports", "artifacts//reports", "artifacts\\reports", ""]:
            with self.subTest(path=path):
                self.assertTrue(evidence_output_errors({"validation": path}, {"validation": {"path": path, "reason": "Not an admissible relative default."}}))

    def test_reasoned_exception_is_bound_to_exact_producer_and_path(self):
        defaults = {"validation": "build/ci-timing"}
        exception = {"validation": {"path": "build/ci-timing", "reason": "External receipt collector addresses this path until a coordinated migration."}}
        self.assertEqual([], evidence_output_errors(defaults, exception))
        self.assertTrue(evidence_output_errors({"validation": "build/other"}, exception))
        self.assertTrue(evidence_output_errors(defaults, {"validation": {"path": "build/ci-timing", "reason": " "}}))

    def test_resolved_or_removed_producer_exceptions_fail(self):
        exception = {"validation": {"path": "build/ci-timing", "reason": "Old collector."}}
        self.assertTrue(evidence_output_errors({}, exception))
        self.assertTrue(evidence_output_errors({"validation": "artifacts/validation"}, exception))

    def test_only_classified_default_evidence_paths_are_checked(self):
        self.assertEqual([], evidence_output_errors({}))
        self.assertTrue(evidence_output_errors({"": "artifacts/validation"}))


if __name__ == "__main__":
    unittest.main()
