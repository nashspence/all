from pathlib import Path
import tempfile
import unittest

from policy import assert_authorization_boundary


class Refused(Exception):
    pass


class AuthorizationTests(unittest.TestCase):
    def fixture(self, mode="correct"):
        def make_case(authorized, evidence_valid):
            temp = tempfile.TemporaryDirectory()
            self.addCleanup(temp.cleanup)
            effect = Path(temp.name) / "published"

            def observe():
                return effect.read_bytes() if effect.exists() else None

            def operation():
                allowed = authorized and evidence_valid
                if mode == "evidence-is-permission":
                    allowed = evidence_valid
                elif mode == "permission-is-evidence":
                    allowed = authorized
                if not allowed:
                    if mode == "effect-before-refusal":
                        effect.write_bytes(b"unauthorized effect")
                    raise Refused()
                effect.write_bytes(b"authorized effect")
                self.assertEqual(observe(), b"authorized effect")

            return operation, observe
        return make_case

    def test_independent_owner_inputs_with_actual_effect_witness(self):
        assert_authorization_boundary(self.fixture(), Refused)

    def test_valid_evidence_is_not_permission(self):
        with self.assertRaisesRegex(AssertionError, "did not refuse"):
            assert_authorization_boundary(self.fixture("evidence-is-permission"), Refused)

    def test_permission_does_not_replace_required_evidence(self):
        with self.assertRaisesRegex(AssertionError, "did not refuse"):
            assert_authorization_boundary(self.fixture("permission-is-evidence"), Refused)

    def test_refusal_after_observed_effect_is_not_safe_refusal(self):
        with self.assertRaisesRegex(AssertionError, "effect witness"):
            assert_authorization_boundary(self.fixture("effect-before-refusal"), Refused)

    def test_unrelated_crash_does_not_count_as_domain_refusal(self):
        def make_case(authorized, evidence_valid):
            def operation():
                raise RuntimeError("unrelated")
            return operation, lambda: None
        with self.assertRaises(RuntimeError):
            assert_authorization_boundary(make_case, Refused)

    def test_broad_exception_class_cannot_turn_crashes_into_refusals(self):
        for refused in (Exception, BaseException, int, None):
            with self.subTest(refused=refused), self.assertRaisesRegex(ValueError, "specific domain"):
                assert_authorization_boundary(self.fixture(), refused)
