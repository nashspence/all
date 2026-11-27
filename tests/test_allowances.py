"""Synthetic adoption contracts through the real shared clock and verifiers.

The small file-writing product exercises observable feature work. Its numbers
are test inputs, not approved consumer budgets or component-cost measurements.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from all_policy.performance.allowances import (
    FEATURES, compile_limits, require_activity, validate_witness,
)
from all_policy.performance.contracts import BINDINGS_PATH, LIMITS_PATH, load_authority
from all_policy.performance.profiles import CAPS_NS, CORE
from all_policy.performance.runner import run_suite


PRODUCT = '''import json
import os
from pathlib import Path
import time

def run(subject, work, repeat):
    selected = json.loads(os.environ["ALL_PERFORMANCE_FEATURES"])
    behavior = json.loads((Path(subject) / "behavior.json").read_text())
    directory = Path(work) / ("repeat-" + str(repeat))
    directory.mkdir()
    total = 0
    for unit in (1, 2):
        total += unit
        if selected["progress"]:
            with (directory / "progress.events").open("a") as output:
                output.write(str(unit) + "\\n")
        if selected["resumability"] and unit % 2 == 0 and not behavior.get("skip_checkpoint"):
            (directory / "checkpoint.json").write_text(json.dumps({"unit": unit, "total": total}))
        if selected["logging"] or behavior.get("force_logging"):
            with (directory / "logging.events").open("a") as output:
                output.write("completed:" + str(unit) + "\\n")
    if selected["progress"] and repeat == 1 and behavior.get("periodic_stall"):
        time.sleep(0.2)
    (directory / "result.json").write_text(json.dumps({"repeat": repeat, "total": total}))
    return {"elapsed_ns": 1, "max_wall_ns": 999999999999, "exercised": True}
'''

EXTRACTOR = '''import json
from pathlib import Path

def extract(work, repeat):
    directory = Path(work) / ("repeat-" + str(repeat))
    assert json.loads((directory / "result.json").read_text()) == {"repeat": repeat, "total": 3}
    counts = {"progress": 0, "resumability": 0, "logging": 0}
    for feature, expected in (("progress", ["1", "2"]), ("logging", ["completed:1", "completed:2"])):
        path = directory / (feature + ".events")
        if path.exists():
            events = path.read_text().splitlines()
            assert events == expected
            counts[feature] = len(events)
    checkpoint = directory / "checkpoint.json"
    if checkpoint.exists():
        assert json.loads(checkpoint.read_text()) == {"unit": 2, "total": 3}
        counts["resumability"] = 1
    return {"verified": True, "activity": counts}
'''

COMMAND = '''import json
import os
from pathlib import Path
import sys
from extractor import extract
from product import run

mode, subject, work, repeat = sys.argv[1:]
repeat = int(repeat)
if mode == "run":
    run(subject, work, repeat)
elif mode == "verify":
    print("checking completed synthetic output", file=sys.stderr)
    print(json.dumps(extract(work, repeat)))
elif mode == "plain-run":
    assert "ALL_PERFORMANCE_FEATURES" not in os.environ
    (Path(work) / ("plain-" + str(repeat))).write_text("closed")
elif mode == "plain-verify":
    assert "ALL_PERFORMANCE_FEATURES" not in os.environ
    assert (Path(work) / ("plain-" + str(repeat))).read_text() == "closed"
'''

ADAPTER = '''from extractor import extract
from product import run as product_run

def prepare(subject, work):
    return subject, work

def run(context, repeat):
    return product_run(*context, repeat)

def verify(context, result, repeat):
    return extract(context[1], repeat)
'''


def admitted_evidence():
    metadata = dict(system="Linux", machine="x86_64", python="3.11.9", logical_cpus=4,
                    affinity_count=4, memory_total_bytes=16 * 1024**3,
                    memory_max="max", cpu_max="max 100000", free_bytes=1024**3,
                    root="/synthetic-storage", device=1, topology={"blockdevices": []},
                    mount={"fstype": "ext4", "source": "/dev/example", "options": "rw,relatime"})
    return dict(metadata=metadata, metadata_after=copy.deepcopy(metadata), errors=[],
                samples_ns={name: [1_000_000] * 3 for name in CAPS_NS})


class AllowanceCompilerTests(unittest.TestCase):
    def test_canonical_envelopes_zero_allowance_and_inapplicability(self):
        document, selections = compile_limits("write", CORE, 100,
                                             dict(progress=0, resumability=20, logging=30))
        self.assertEqual(document, {"schema": 1, "operations": {
            "write_core": {"profile": CORE, "max_wall_ns": 100},
            "write_progress": {"profile": CORE, "max_wall_ns": 100},
            "write_resumability": {"profile": CORE, "max_wall_ns": 120},
            "write_logging": {"profile": CORE, "max_wall_ns": 130},
            "write_all": {"profile": CORE, "max_wall_ns": 150}}})
        self.assertEqual(selections, {"write_core": (), "write_progress": ("progress",),
                                     "write_resumability": ("resumability",),
                                     "write_logging": ("logging",), "write_all": FEATURES})
        only, selected = compile_limits("write", CORE, 100,
                                      dict(progress=0, resumability=None, logging=None))
        self.assertEqual(set(only["operations"]), {"write_core", "write_progress"})
        self.assertEqual(selected, {"write_core": (), "write_progress": ("progress",)})
        none, selected = compile_limits("write", CORE, 100, dict.fromkeys(FEATURES))
        self.assertEqual(set(none["operations"]), {"write_core"})
        self.assertEqual(selected, {"write_core": ()})

    def test_declarations_reject_implicit_applicability_and_noninteger_allowances(self):
        valid = dict(progress=10, resumability=None, logging=0)
        cases = [("write", CORE, value, valid) for value in (True, 0, -1, 1.0, "100")]
        cases += [("write", CORE, 100, value) for value in (
            None, [], {}, {"progress": 10}, dict(valid, extra=1),
            dict(valid, progress=True), dict(valid, progress=-1),
            dict(valid, logging=1.0), dict(valid, resumability="0"))]
        cases += [(name, CORE, 100, valid) for name in (None, "", "Bad", "x" * 68)]
        cases += [("write", profile, 100, valid) for profile in ("unknown", None, [])]
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                compile_limits(*arguments)

    def test_witness_checks_actual_activity_and_strict_shape(self):
        counts = dict(progress=2, resumability=0, logging=0)
        require_activity(("progress",), counts)
        validate_witness(("progress",), {"verified": True, "activity": counts})
        invalid_counts = [dict(counts, progress=0), dict(counts, logging=1),
                          dict(counts, progress=True), dict(counts, progress=-1),
                          dict(counts, progress=1.0), {"progress": 2}]
        for value in invalid_counts:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_witness(("progress",), {"verified": True, "activity": value})
        for value in (True, {"exercised": True}, {"verified": 1, "activity": counts},
                      {"verified": False, "activity": counts},
                      {"verified": True, "activity": counts, "elapsed_ns": 1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_witness(("progress",), value)
        for enabled in (("progress", "progress"), ("unknown",), "progress"):
            with self.subTest(enabled=enabled), self.assertRaises(ValueError):
                require_activity(enabled, counts)

    def test_configuration_headroom_is_not_a_component_cost_measurement(self):
        limits, _ = compile_limits("write", CORE, 100, dict(progress=10, resumability=None, logging=None))
        # Hypothetical component costs demonstrate only the arithmetic limitation.
        # These values are deliberately not presented as collected observations.
        hypothetical_core, hypothetical_progress = 60, 40
        self.assertGreater(hypothetical_progress, 10)
        self.assertLessEqual(hypothetical_core + hypothetical_progress,
                             limits["operations"]["write_progress"]["max_wall_ns"])


class AllowanceIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.subject = self.root / "candidate"
        self.subject.mkdir()
        self.storage = self.root / "storage"
        self.storage.mkdir()
        subprocess.run(["git", "init", "-q", str(self.subject)], check=True)
        for name, content in (("product.py", PRODUCT), ("extractor.py", EXTRACTOR),
                              ("command.py", COMMAND), ("adapter.py", ADAPTER)):
            (self.subject / name).write_text(content)
        self.behavior()

    def commit(self):
        subprocess.run(["git", "-C", str(self.subject), "add", "--all"], check=True)
        subprocess.run(["git", "-C", str(self.subject), "-c", "user.name=Local Test",
                        "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture"],
                       check=True)
        return subprocess.check_output(["git", "-C", str(self.subject), "rev-parse", "HEAD"],
                                       text=True).strip()

    def behavior(self, **values):
        (self.subject / "behavior.json").write_text(json.dumps(values))

    def documents(self, optional=None, warm_core=1_000_000_000, ordinary=False):
        optional = optional if optional is not None else dict.fromkeys(FEATURES, 0)
        limits = {"schema": 2, "operations": {
            "cold": {"profile": CORE, "core_ns": 1_000_000_000, "optional_ns": optional},
            "warm": {"profile": CORE, "core_ns": warm_core, "optional_ns": optional}}}
        digest = lambda name: hashlib.sha256((self.subject / name).read_bytes()).hexdigest()
        files = {name: digest(name) for name in ("command.py", "adapter.py", "extractor.py")}
        bindings = {"schema": 1, "repository": "nashspence/example", "operations": {}}
        for group, row in limits["operations"].items():
            _, selections = compile_limits(group, **row)
            for name, features in selections.items():
                common = dict(unit="two complete synthetic file updates",
                              completion="required output and all selected feature files closed",
                              approved_files=files, features=list(features))
                suffix = name[len(group):]
                if group == "cold":
                    common.update(mode="command",
                                  command=["{python}", "{subject}/command.py", "run", "{subject}", "{work}", "{repeat}"],
                                  verify=["{python}", "{subject}/command.py", "verify", "{subject}", "{work}", "{repeat}"])
                else:
                    common.update(mode="request", adapter="adapter.py", cold_operation="cold" + suffix)
                bindings["operations"][name] = common
        if ordinary:
            limits["operations"]["plain"] = dict(profile=CORE, max_wall_ns=1_000_000_000)
            bindings["operations"]["plain"] = dict(
                mode="command", unit="one legacy command", completion="output closed", approved_files=files,
                command=["{python}", "{subject}/command.py", "plain-run", "{subject}", "{work}", "{repeat}"],
                verify=["{python}", "{subject}/command.py", "plain-verify", "{subject}", "{work}", "{repeat}"])
        return limits, bindings

    def pin(self, limits, bindings):
        for relative, value in ((LIMITS_PATH, limits), (BINDINGS_PATH, bindings)):
            path = self.subject / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
        return self.commit()

    def authority(self, **options):
        limits, bindings = self.documents(**options)
        revision = self.pin(limits, bindings)
        return load_authority(self.subject, revision, "nashspence/example")

    def run_admitted(self, authority):
        # All product execution, source checks, timers and witnesses are real.
        # Only the separately-tested shared authority and environmental probe
        # are substituted; this is not an admitted profile qualification run.
        with patch("all_policy.performance.runner.require_current", return_value={CORE: {"status": "active"}}), \
                patch("all_policy.performance.runner._preflight", return_value=admitted_evidence()):
            return run_suite(authority, self.subject, {CORE: self.storage})

    def test_pinned_modes_drive_cold_and_warm_production_and_reviewed_witnesses(self):
        authority = self.authority(ordinary=True)
        with patch.dict("os.environ", {"ALL_PERFORMANCE_FEATURES": '{"logging":true,"invented":true}'}):
            result = self.run_admitted(authority)
        self.assertEqual(result["verdict"], "pass", result)
        self.assertEqual(len(result["operations"]), 11)
        expected = {"core": (), "progress": ("progress",), "resumability": ("resumability",),
                    "logging": ("logging",), "all": FEATURES}
        for suffix, features in expected.items():
            for group in ("cold", "warm"):
                row = result["operations"][group + "_" + suffix]
                with self.subTest(group=group, suffix=suffix):
                    self.assertEqual(row["features"], list(features))
                    self.assertEqual(len(row["observations"]), 3)
                    for observation in row["observations"]:
                        counts = {feature: (1 if feature == "resumability" else 2)
                                  if feature in features else 0 for feature in FEATURES}
                        self.assertEqual(observation["feature_witness"], {"verified": True, "activity": counts})
                        self.assertTrue(observation["completed"] and observation["verified"])
                        self.assertGreater(observation["elapsed_ns"], 1)
        self.assertNotIn("feature_witness", result["operations"]["plain"]["observations"][0])

    def test_pinned_expansion_rejects_missing_mislabeled_extra_and_mismatched_modes(self):
        limits, bindings = self.documents()
        mutations = []
        missing = copy.deepcopy(bindings)
        del missing["operations"]["warm_all"]
        mutations.append((limits, missing))
        mislabeled = copy.deepcopy(bindings)
        mislabeled["operations"]["warm_progress"]["features"] = ["logging"]
        mutations.append((limits, mislabeled))
        absent = copy.deepcopy(bindings)
        del absent["operations"]["cold_core"]["features"]
        mutations.append((limits, absent))
        extra = copy.deepcopy(bindings)
        extra["operations"]["invented"] = copy.deepcopy(extra["operations"]["cold_core"])
        mutations.append((limits, extra))
        counterpart = copy.deepcopy(bindings)
        counterpart["operations"]["warm_progress"]["cold_operation"] = "cold_core"
        mutations.append((limits, counterpart))
        legacy_limits = {"schema": 1, "operations": {"plain": dict(profile=CORE, max_wall_ns=100)}}
        legacy_bindings = dict(schema=1, repository="nashspence/example", operations={
            "plain": copy.deepcopy(bindings["operations"]["cold_core"])})
        mutations.append((legacy_limits, legacy_bindings))
        for number, (declaration, bound) in enumerate(mutations):
            with self.subTest(case=number):
                revision = self.pin(declaration, bound)
                with self.assertRaises(ValueError):
                    load_authority(self.subject, revision, "nashspence/example")

    def test_expanded_inventory_is_bounded_and_collisions_rejected(self):
        limits, bindings = self.documents()
        collision = copy.deepcopy(limits)
        collision["operations"]["cold_core"] = dict(profile=CORE, max_wall_ns=1)
        revision = self.pin(collision, bindings)
        with self.assertRaises(ValueError):
            load_authority(self.subject, revision, "nashspence/example")
        row = limits["operations"]["cold"]
        crowded = {"schema": 2, "operations": {"op" + str(i): copy.deepcopy(row) for i in range(7)}}
        all_bindings = copy.deepcopy(bindings)
        all_bindings["operations"] = {}
        for group in crowded["operations"]:
            _, selections = compile_limits(group, **row)
            for name, features in selections.items():
                spec = copy.deepcopy(bindings["operations"]["cold_core"])
                spec["features"] = list(features)
                all_bindings["operations"][name] = spec
        revision = self.pin(crowded, all_bindings)
        with self.assertRaises(ValueError):
            load_authority(self.subject, revision, "nashspence/example")

    def test_real_miss_survives_candidate_budget_change_and_false_timing_claim(self):
        authority = self.authority(optional=dict(progress=0, resumability=None, logging=None),
                                   warm_core=100_000_000)
        self.behavior(periodic_stall=True)
        proposal_path = self.subject / LIMITS_PATH
        proposal = json.loads(proposal_path.read_text())
        proposal["operations"]["warm"]["core_ns"] = 999_999_999_999
        proposal["operations"]["warm"]["optional_ns"]["progress"] = 999_999_999_999
        proposal_path.write_text(json.dumps(proposal))
        candidate = self.commit()
        pinned = load_authority(self.subject, authority.revision, "nashspence/example")
        result = self.run_admitted(pinned)
        self.assertEqual(result["candidate_revision"], candidate)
        self.assertEqual(result["authority_revision"], authority.revision)
        self.assertEqual(result["verdict"], "miss", result)
        row = result["operations"]["warm_progress"]
        decision = row["decision"]
        self.assertEqual(decision["budget_ns"], 100_000_000)
        self.assertEqual(decision["miss_kind"], "mixed")
        self.assertEqual(decision["over_budget_indices"], [1])
        self.assertEqual(len(row["observations"]), 3)
        self.assertGreater(decision["samples_ns"][1], 150_000_000)
        self.assertTrue(all(observation["verified"] for observation in row["observations"]))
        self.assertEqual(result["operations"]["warm_core"]["decision"]["verdict"], "pass")

    def test_unreached_checkpoint_and_disabled_optional_work_fail_correct_fast_results(self):
        for feature, behavior, failed_suffix in (
                ("resumability", {"skip_checkpoint": True}, "resumability"),
                ("progress", {"force_logging": True}, "core")):
            with self.subTest(feature=feature):
                self.behavior(**behavior)
                optional = dict.fromkeys(FEATURES)
                optional[feature] = 0
                authority = self.authority(optional=optional)
                result = self.run_admitted(authority)
                self.assertEqual(result["verdict"], "failed")
                for group in ("cold", "warm"):
                    row = result["operations"][group + "_" + failed_suffix]
                    self.assertEqual(row["decision"]["verdict"], "failed")
                    self.assertTrue(any(observation["completed"] and not observation["verified"]
                                        for observation in row["observations"]))

    def test_opted_verifiers_must_supply_real_witnesses_in_both_modes(self):
        (self.subject / "command.py").write_text(COMMAND.replace(
            'print(json.dumps(extract(work, repeat)))', 'extract(work, repeat)'))
        (self.subject / "adapter.py").write_text(ADAPTER.replace(
            'return extract(context[1], repeat)', 'extract(context[1], repeat)\n    return True'))
        authority = self.authority(optional=dict.fromkeys(FEATURES))
        result = self.run_admitted(authority)
        for row in result["operations"].values():
            self.assertEqual(row["decision"]["verdict"], "failed")
            self.assertTrue(any(observation["completed"] and not observation["verified"]
                                for observation in row["observations"]))

    def test_command_witness_rejects_duplicate_members_noise_and_oversized_output(self):
        replacements = (
            '''print('{"verified":true,"verified":true,"activity":{"progress":0,"resumability":0,"logging":0}}')''',
            'print("not a witness")\n    print(json.dumps(extract(work, repeat)))',
            'print(" " * 65536 + json.dumps(extract(work, repeat)))',
        )
        for number, replacement in enumerate(replacements):
            with self.subTest(case=number):
                (self.subject / "command.py").write_text(COMMAND.replace(
                    'print(json.dumps(extract(work, repeat)))', replacement))
                authority = self.authority(optional=dict.fromkeys(FEATURES))
                result = self.run_admitted(authority)
                cold = result["operations"]["cold_core"]
                self.assertEqual(cold["decision"]["verdict"], "failed")
                self.assertTrue(all(row["completed"] and not row["verified"]
                                    for row in cold["observations"]))
                self.assertEqual(result["operations"]["warm_core"]["decision"]["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
