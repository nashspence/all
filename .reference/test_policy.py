import sys
import unittest
from policy import public_projection, assert_secret_safe

SCHEMA = {
    "phase": frozenset({"complete", "download"}),
    "category": frozenset({"ok", "provider-unavailable"}),
    "passed": bool,
}
PRIVATE = {"credential": "SYNTHETIC-CREDENTIAL-37a9", "endpoint": "SYNTHETIC-PRIVATE-HOST-529d"}


def producer(case, private):
    try:
        if case == "failure":
            raise OSError("provider stderr from " + private["endpoint"] + " using " + private["credential"])
        raw = {"phase": "complete", "category": "ok", "passed": True}
    except OSError as error:
        raw = {
            "phase": "download", "category": "provider-unavailable", "passed": False,
            "stderr": str(error), "environment": private,
        }
    return public_projection(raw, SCHEMA)


class SafeDiagnosticTests(unittest.TestCase):
    def check(self, callback=producer):
        return assert_secret_safe(callback, private_inputs=PRIVATE, cases=["success", "failure"], schema=SCHEMA)

    def test_actual_success_failure_paths_keep_actionable_categories(self):
        results = self.check()
        self.assertEqual([record["category"] for record in results], ["ok", "provider-unavailable"])
        self.assertEqual([record["passed"] for record in results], [True, False])

    def test_copied_provider_stderr_is_rejected(self):
        def leak(case, private):
            record = producer(case, private)
            record["stderr"] = private["credential"]
            return record
        with self.assertRaisesRegex(AssertionError, "private input"):
            self.check(leak)

    def test_public_stream_leak_is_rejected(self):
        def leak(case, private):
            print(private["endpoint"], file=sys.stderr)
            return producer(case, private)
        with self.assertRaisesRegex(AssertionError, "private input"):
            self.check(leak)

    def test_unlisted_fields_and_unbounded_category_are_rejected(self):
        def extra(case, private):
            return {**producer(case, private), "argv": "even a harmless copied argument"}
        with self.assertRaisesRegex(AssertionError, "outside"):
            self.check(extra)
        with self.assertRaises(ValueError):
            public_projection({"phase": "complete", "category": "arbitrary provider text", "passed": False}, SCHEMA)

    def test_exception_payload_is_not_silently_safe(self):
        def crash(case, private):
            raise RuntimeError(private["credential"])
        with self.assertRaisesRegex(AssertionError, "private input"):
            self.check(crash)


if __name__ == "__main__":
    unittest.main()
