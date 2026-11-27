"""The admission allowance cannot hide bad evidence or a measured budget miss."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from all_policy.performance import runner
from all_policy.performance.approval import ApprovalError, source_digest
from all_policy.performance.contracts import Limit, evaluate
from all_policy.performance.profiles import CAPS_NS, CORE, admit
from all_policy.performance.refresh_collect import AUTHORITY, DOCUMENTS, LIMITS, classify
from test_performance import evidence


SOURCE = "a" * 40


def packet(preflight=None):
    preflight = evidence() if preflight is None else copy.deepcopy(preflight)
    for phase in ("metadata", "metadata_after"):
        preflight[phase].update(cpu_model="Qualification fixture CPU", image_os="ubuntu24",
                                image_version="fixture-image-version")
    admission = admit(CORE, preflight)
    operations = {}
    for name, cap in LIMITS.items():
        samples = [{"elapsed_ns": cap // 2, "completed": True, "verified": True}
                   for unused in range(3)] if admission["admitted"] else []
        operations[name] = {
            "admission": admission, "observations": samples,
            "decision": evaluate(Limit(CORE, cap), admission, samples),
            "excluded_stages": {}, "mode": "request" if name.endswith("warm") else "command",
            "unit": "sixteen actual policy checks", "completion": "all checks returned"}
    return {"schema": 1, "qualification_only": True, "source_commit": SOURCE,
            "source_digest": source_digest(), "error": None,
            "raw": {"schema": 1, "authority_revision": AUTHORITY, "repository": "nashspence/all",
                    "candidate_revision": SOURCE, "limits_sha256": DOCUMENTS["limits"],
                    "bindings_sha256": DOCUMENTS["bindings"], "shared_source": runner.source_info(),
                    "preflights": {"/work": preflight}, "operations": operations,
                    "verdict": "pass" if admission["admitted"] else "unqualified", "total_ns": 1}}


class RefreshCollectorTests(unittest.TestCase):
    def classify(self, value):
        return classify(value, "core", source_digest())

    def test_complete_correct_environmental_rejection_is_the_only_tolerated_case(self):
        self.assertEqual(self.classify(packet()), "pass")
        preflight = evidence()
        preflight["samples_ns"]["cpu_serial"][0] = CAPS_NS["cpu_serial"] + 1
        rejected = packet(preflight)
        self.assertEqual(self.classify(rejected), "environment")
        self.assertTrue(all(row["observations"] == [] for row in rejected["raw"]["operations"].values()))
        rejected["raw"]["operations"]["check_repository16_warm"]["observations"] = [
            {"elapsed_ns": 1, "completed": True, "verified": True}]
        self.assertEqual(self.classify(rejected), "incomplete")

    def test_probe_errors_missing_samples_and_malformed_metadata_are_incomplete(self):
        mutations = (
            lambda ev: ev["errors"].append({"probe": "cpu_serial", "repeat": 0, "error": "wrong result"}),
            lambda ev: ev["samples_ns"]["cpu_serial"].pop(),
            lambda ev: ev["metadata"].pop("cpu_model"),
            lambda ev: ev["metadata"].update(logical_cpus=True),
            lambda ev: ev["metadata"].update(cpu_max="garbage"),
            lambda ev: ev["metadata"].update(memory_max="garbage"),
            lambda ev: ev["metadata"].pop("cpu_max"),
            lambda ev: ev["metadata_after"]["mount"].update(source="/changed"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                value = packet()
                ev = value["raw"]["preflights"]["/work"]
                mutation(ev)
                # Recompute ordinary rejection honestly. It still cannot consume
                # the availability allowance when its underlying evidence is bad.
                admission = admit(CORE, ev)
                for name, row in value["raw"]["operations"].items():
                    row["admission"] = admission
                    if not admission["admitted"]:
                        row["observations"] = []
                    row["decision"] = evaluate(Limit(CORE, LIMITS[name]), admission, row["observations"])
                value["raw"]["verdict"] = "pass" if admission["admitted"] else "unqualified"
                self.assertEqual(self.classify(value), "incomplete")

    def test_measured_miss_is_failed_even_with_fast_other_observations(self):
        value = packet()
        name = "check_repository16_warm"
        row = value["raw"]["operations"][name]
        row["observations"][0]["elapsed_ns"] = LIMITS[name] + 1
        row["decision"] = evaluate(Limit(CORE, LIMITS[name]), row["admission"], row["observations"])
        value["raw"]["verdict"] = "miss"
        self.assertLess(row["decision"]["raw_mean_ns"], LIMITS[name])
        self.assertEqual(self.classify(value), "failed")

    def test_exact_authority_source_and_actual_shared_hashes_are_required(self):
        mutations = (
            lambda value: value["raw"].update(authority_revision="b" * 40),
            lambda value: value["raw"].update(bindings_sha256="b" * 64),
            lambda value: value["raw"].update(limits_sha256="b" * 64),
            lambda value: value["raw"].update(candidate_revision="b" * 40),
            lambda value: value.update(source_digest="b" * 64),
            lambda value: value["raw"].pop("shared_source"),
            lambda value: value["raw"]["shared_source"].update(package_sha256="b" * 64),
            lambda value: value["raw"]["shared_source"]["files_sha256"].update({"runner.py": "b" * 64}),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                value = packet()
                mutation(value)
                self.assertEqual(self.classify(value), "incomplete")

    def test_normal_runner_requires_current_approval_before_any_measurement(self):
        authority = SimpleNamespace(limits={"work": Limit(CORE, 100)})
        with patch.object(runner, "require_current", side_effect=ApprovalError("suspended")) as approval, \
             patch.object(runner, "_ProcessScope") as scope, \
             patch.object(runner, "_run_suite") as measure:
            with self.assertRaisesRegex(ApprovalError, "suspended"):
                runner.run_suite(authority, "unused-subject", {CORE: "unused-storage"})
            approval.assert_called_once_with({CORE})
            scope.assert_not_called()
            measure.assert_not_called()
        proof = {CORE: {"status": "active", "registry_commit": SOURCE}}
        with patch.object(runner, "require_current", return_value=proof), \
             patch.object(runner, "_ProcessScope"), \
             patch.object(runner, "_run_suite", return_value={"verdict": "pass"}):
            result = runner.run_suite(authority, "unused-subject", {CORE: "unused-storage"})
            self.assertEqual(result["profile_approval"], proof)


if __name__ == "__main__":
    unittest.main()
