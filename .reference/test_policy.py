"""Synthetic owner binding and bounded counterexamples, not consumer qualification."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
import sys
import unittest

from policy import Controls, FEATURES


def operation(controls, events, *, authority=True, cancelled=False, eager=False):
    """A single execution path; checkpoints save replay work, commits protect results."""

    def optional(feature):
        # The first event represents the producer's work, not just its output sink.
        events.append((feature, "prepare"))
        events.append((feature, "complete"))

    try:
        if not authority:
            raise PermissionError("required authority absent")
        if cancelled:
            raise InterruptedError("operation cancelled")
        events.append(("core", "useful-result"))
        if eager:
            optional("progress")
        controls.call("progress", lambda: optional("progress"))
        controls.call("resumability", lambda: optional("resumability"))
        controls.call("logging", lambda: optional("logging"))
        events.append(("core", "required-commit"))
        events.append(("core", "mandatory-audit"))
        return b"accepted-result"
    except (PermissionError, InterruptedError):
        events.append(("core", "error-result"))
        raise
    finally:
        events.append(("core", "resource-release"))


def assert_observed(test, controls, events, expected_result):
    test.assertEqual(expected_result, b"accepted-result")
    test.assertEqual(
        [action for owner, action in events if owner == "core"],
        ["useful-result", "required-commit", "mandatory-audit", "resource-release"],
    )
    for feature in FEATURES:
        test.assertEqual(
            [action for owner, action in events if owner == feature],
            ["prepare", "complete"] if feature in controls.enabled else [],
        )


class ControlsTests(unittest.TestCase):
    def test_global_and_individual_off_leave_required_result_and_commit(self):
        for controls in [
            Controls(),
            Controls.all_off(),
            *(Controls().without(feature) for feature in sorted(FEATURES)),
        ]:
            with self.subTest(enabled=sorted(controls.enabled)):
                events = []
                result = operation(controls, events)
                assert_observed(self, controls, events, result)

    def test_disabled_producer_is_not_called(self):
        def forbidden_preparation():
            self.fail("disabled producer performed work before its output sink")

        for feature in FEATURES:
            self.assertIsNone(Controls.all_off().call(feature, forbidden_preparation))

    def test_eager_work_and_ignored_parent_fail_the_same_behavioral_witness(self):
        controls = Controls.all_off()
        events = []
        result = operation(controls, events, eager=True)
        with self.assertRaises(AssertionError):
            assert_observed(self, controls, events, result)

        events = []
        result = operation(Controls(), events)  # Mutant discards inherited all-off.
        with self.assertRaises(AssertionError):
            assert_observed(self, controls, events, result)

    def test_child_defaults_cannot_reenable_parent_and_request_can_narrow(self):
        parent = Controls().without("progress")
        self.assertEqual(parent.child(Controls()), parent)
        self.assertEqual(Controls.all_off().child(Controls()), Controls.all_off())
        self.assertEqual(
            parent.child(Controls().without("logging")).enabled,
            frozenset({"resumability"}),
        )

        # Explicit transport to one actual child; no mutable process-global flag.
        program = """
import json, sys
sys.path.insert(0, sys.argv[1])
from policy import Controls
parent = Controls(frozenset(json.loads(sys.argv[2])))
effective = parent.child(Controls())
started = []
for feature in ('progress', 'resumability', 'logging'):
    effective.call(feature, lambda name=feature: started.append(name))
print(json.dumps(started))
"""
        child = subprocess.run(
            [
                sys.executable, "-I", "-c", program,
                str(Path(__file__).resolve().parent),
                json.dumps(sorted(parent.enabled)),
            ],
            check=True, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(json.loads(child.stdout), ["resumability", "logging"])

    def test_all_off_keeps_required_failure_and_cancellation_outcomes(self):
        for arguments, error in [
            ({"authority": False}, PermissionError),
            ({"cancelled": True}, InterruptedError),
        ]:
            with self.subTest(arguments=arguments):
                events = []
                with self.assertRaises(error):
                    operation(Controls.all_off(), events, **arguments)
                self.assertEqual(events, [
                    ("core", "error-result"), ("core", "resource-release"),
                ])

    def test_policy_is_immutable_and_unknown_features_cannot_be_silenced(self):
        with self.assertRaises(FrozenInstanceError):
            Controls().enabled = frozenset()
        with self.assertRaises(TypeError):
            Controls(set(FEATURES))
        with self.assertRaises(ValueError):
            Controls(frozenset({"required-commit"}))
        with self.assertRaises(ValueError):
            Controls().without("required-commit")
        with self.assertRaises(ValueError):
            Controls.all_off().call("required-commit", lambda: None)


if __name__ == "__main__":
    unittest.main()
