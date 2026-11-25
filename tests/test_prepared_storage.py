"""Fail-closed resource custody/admission controls, not hardware qualification.

These tests use synthetic metadata where stated and never mount or format a
device. Real native setup, timings and physical failure claims require their
separately retained evidence; mocked metadata cannot provide that evidence.
"""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from all_policy.performance import prepared_storage as storage
from all_policy.performance import profiles


def synthetic_pair():
    """A complete inspector-shaped record for testing admission decisions only."""
    base = "/var/lib/all-policy-66/synthetic"
    roots = {"root_loop_a": base + "/a.mount", "root_loop_b": base + "/b.mount"}
    mounts = {role: {"target": root, "source": "/dev/loop" + str(i + 7), "fstype": "ext4",
                     "options": "rw,nosuid,nodev,noatime,data=ordered,max_batch_time=0",
                     "maj:min": "7:" + str(i + 7)}
              for i, (role, root) in enumerate(roots.items())}
    observations = {}
    for i, (role, root) in enumerate(roots.items()):
        prepared = {"profile": profiles.PREPARED_EXT4, "errors": [],
                    "physical_persistence_proven": False,
                    "manifest_path": base + "/resource.json", "manifest_sha256": "a" * 64,
                    "manifest_identity": {"uid": 0, "gid": 0, "mode": 0o400, "nlink": 1},
                    "preparation_source_sha256": "b" * 64, "current_source_sha256": "b" * 64,
                    "binding_sha256": str(i + 1) * 64, "resource_roots": roots,
                    "selected_role": role, "selected_root": root, "selected_mount": mounts[role],
                    "verification": {"status": "verified", "mounts": {
                        "a": {"mount": mounts["root_loop_a"]}, "b": {"mount": mounts["root_loop_b"]}}}}
        metadata = {"system": "Linux", "machine": "x86_64", "python": "3.12.16",
                    "logical_cpus": 4, "affinity_count": 4, "memory_total_bytes": 16 * 1024**3,
                    "memory_max": "max", "cpu_max": "max 100000", "free_bytes": 128 * 1024**2,
                    "image_os": "ubuntu24", "root": root, "device": i + 7,
                    "mount": mounts[role], "topology": {"blockdevices": []},
                    "prepared_storage": prepared}
        observations[role] = {"metadata": metadata, "metadata_after": copy.deepcopy(metadata),
                              "errors": [], "samples_ns": {key: [1_000_000] * 3 for key in profiles.CAPS_NS}}
    result = observations["root_loop_a"]
    result["prepared_pair"] = {"counterpart_role": "root_loop_b", "counterpart_root": roots["root_loop_b"],
                               "evidence": observations["root_loop_b"]}
    return result


class PreparedStorageTests(unittest.TestCase):
    def test_unrelated_path_and_noncanonical_manifest_cannot_claim_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(storage, "_load_manifest") as load:
                record = storage.inspect(directory)
            self.assertTrue(record["errors"])
            self.assertFalse(record["physical_persistence_proven"])
            load.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "canonical protected"):
                storage._load_manifest(Path(directory) / "resource.json")

    def test_setup_refuses_wrong_workflow_context_before_any_storage_command(self):
        environment = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                       "RUNNER_OS": "Linux", "ImageOS": "ubuntu24", "GITHUB_REPOSITORY": "nashspence/example",
                       "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "push",
                       "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
                       "GITHUB_SHA": "a" * 40, "RUNNER_NAME": "test-worker"}
        cases = ({"GITHUB_REPOSITORY": "someone/else"}, {"GITHUB_REF": "refs/heads/proposal"},
                 {"RUNNER_ENVIRONMENT": "self-hosted"}, {"GITHUB_EVENT_NAME": "pull_request"})
        for changed in cases:
            with self.subTest(changed=changed), patch.dict(os.environ, environment | changed, clear=True), \
                    patch.object(storage.os, "geteuid", return_value=0), \
                    patch.object(storage.os, "getegid", return_value=0), \
                    patch.object(storage, "_command") as command, \
                    patch.object(storage, "_mount") as mount:
                context = {"expected_repository": "nashspence/example", "allowed_refs": ["refs/heads/main"],
                           "worker_id": "1"}
                with self.assertRaises(RuntimeError):
                    storage._setup(context, None)
                command.assert_not_called()
                mount.assert_not_called()

    def test_schedule_requires_main_even_when_another_branch_is_allowlisted(self):
        environment = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                       "RUNNER_OS": "Linux", "ImageOS": "ubuntu24", "GITHUB_REPOSITORY": "nashspence/example",
                       "GITHUB_REF": "refs/heads/proposal", "GITHUB_EVENT_NAME": "schedule"}
        with patch.dict(os.environ, environment, clear=True), \
                patch.object(storage.os, "geteuid", return_value=0), \
                patch.object(storage.os, "getegid", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "main-ref schedules"):
                storage._guard({"expected_repository": "nashspence/example",
                                "allowed_refs": ["refs/heads/proposal"], "worker_id": "1"})

    def test_direct_io_or_writable_flag_cannot_be_replaced_by_success_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "owned.img"
            image.touch()
            identity = {"dev": os.makedev(8, 1), "ino": 17}
            row = {"name": "/dev/loop7", "back-file": str(image), "back-ino": 17,
                   "back-maj:min": "8:1", "dio": True, "ro": False, "offset": 0, "sizelimit": 0}
            for changed in ({"dio": False}, {"ro": True}):
                with self.subTest(changed=changed), \
                        patch.object(storage, "_same_identity", return_value=identity), \
                        patch.object(storage, "_associated", return_value=[row | changed]):
                    with self.assertRaisesRegex(RuntimeError, "writable direct I/O"):
                        storage._loop_identity({}, None, {"image": str(image), "image_identity": identity})

    def test_inspection_binds_requested_root_to_the_actual_enrolled_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            session = base / "session"
            a, b, native = (session / name for name in ("a.mount", "b.mount", "native"))
            for path in (a, b, native):
                path.mkdir(parents=True)
            context = {"root_loop_a": str(a), "root_loop_b": str(b),
                       "images": [{"label": "a", "mount": {"maj:min": "7:7"}},
                                  {"label": "b", "mount": {"maj:min": "7:8"}}]}
            with patch.object(storage, "BASE", base), \
                    patch.object(storage, "_load_manifest", return_value=context), \
                    patch.object(storage, "_verify"), \
                    patch.object(storage, "_mount", return_value={"target": str(b), "maj:min": "7:8"}):
                wrong_mount = storage.inspect(a)
                wrong_subtree = storage.inspect(native)
            self.assertTrue(any("not the enrolled filesystem" in e for e in wrong_mount["errors"]))
            self.assertTrue(any("not on either prepared loop" in e for e in wrong_subtree["errors"]))

    def test_complete_synthetic_pair_admits_timing_without_certifying_persistence(self):
        evidence = synthetic_pair()
        admitted = profiles.admit(profiles.PREPARED_EXT4, evidence)
        self.assertTrue(admitted["admitted"], admitted["reasons"])
        self.assertFalse(admitted["persistence_qualified"])
        self.assertEqual(profiles.PROFILES[profiles.PREPARED_EXT4].probe_runtime, "3.12.16")
        evidence["physical_persistence_proven"] = True
        self.assertFalse(profiles.admit(profiles.PREPARED_EXT4, evidence)["persistence_qualified"])

    def test_fast_samples_do_not_replace_custody_mount_evidence_or_correct_runtime(self):
        mutations = (
            lambda row: row.pop("prepared_storage"),
            lambda row: row["prepared_storage"].pop("manifest_identity"),
            lambda row: row["prepared_storage"]["manifest_identity"].update(mode=0o644),
            lambda row: row["prepared_storage"].update(errors=["effective mount options changed"]),
            lambda row: row["mount"].pop("options"),
            lambda row: row["prepared_storage"].update(selected_root="/somewhere/else"),
            lambda row: row["prepared_storage"].update(current_source_sha256="c" * 64),
            lambda row: row.update(python="3.11.9"),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                evidence = synthetic_pair()
                evidence["profile_approved"] = True
                for key in ("metadata", "metadata_after"):
                    mutate(evidence[key])
                self.assertFalse(profiles.admit(profiles.PREPARED_EXT4, evidence)["admitted"])

    def test_other_filesystem_must_have_complete_same_resource_probe_evidence(self):
        for variant in ("missing", "incomplete", "different_manifest", "wrong_role", "changed_options"):
            with self.subTest(variant=variant):
                evidence = synthetic_pair()
                pair = evidence["prepared_pair"]
                if variant == "missing":
                    evidence.pop("prepared_pair")
                elif variant == "incomplete":
                    pair["evidence"]["samples_ns"]["fdatasync64"].pop()
                elif variant == "different_manifest":
                    for key in ("metadata", "metadata_after"):
                        pair["evidence"][key]["prepared_storage"]["manifest_sha256"] = "d" * 64
                elif variant == "wrong_role":
                    pair["counterpart_role"] = "root_loop_a"
                else:
                    pair["evidence"]["metadata_after"]["mount"]["options"] = "rw,nobarrier"
                self.assertFalse(profiles.admit(profiles.PREPARED_EXT4, evidence)["admitted"])

    def test_prepared_v2_keeps_slow_valid_probes_as_diagnostics(self):
        evidence = synthetic_pair()
        for record in (evidence, evidence["prepared_pair"]["evidence"]):
            record["samples_ns"] = {name: [cap * 4] * 3 for name, cap in profiles.CAPS_NS.items()}
        before = copy.deepcopy(evidence)
        result = profiles.admit(profiles.PREPARED_EXT4, evidence)
        self.assertEqual(profiles.PREPARED_EXT4, "public-linux-x64-4cpu-prepared-ext4-v2")
        self.assertTrue(result["admitted"], result["reasons"])
        self.assertEqual(evidence, before)
        self.assertFalse(result["persistence_qualified"])

    def test_diagnostic_probe_times_still_require_complete_valid_correct_observations(self):
        invalid = ([], [1, 1], [1, 0, 1], [1, True, 1], [1, None, 1], [1, -1, 1])
        for secondary in (False, True):
            for values in invalid:
                with self.subTest(secondary=secondary, values=values):
                    evidence = synthetic_pair()
                    record = evidence["prepared_pair"]["evidence"] if secondary else evidence
                    record["samples_ns"]["fdatasync64"] = list(values)
                    self.assertFalse(profiles.admit(profiles.PREPARED_EXT4, evidence)["admitted"])
            evidence = synthetic_pair()
            record = evidence["prepared_pair"]["evidence"] if secondary else evidence
            record["errors"].append({"probe": "sha256", "repeat": 1, "error": "probe output mismatch"})
            self.assertFalse(profiles.admit(profiles.PREPARED_EXT4, evidence)["admitted"])

    def test_legacy_caps_still_apply_and_failed_prepared_v1_is_not_registered(self):
        evidence = synthetic_pair()
        for key in ("metadata", "metadata_after"):
            evidence[key]["python"] = "3.11.9"
        evidence["samples_ns"]["cpu_serial"][1] = profiles.CAPS_NS["cpu_serial"] + 1
        self.assertFalse(profiles.admit(profiles.NATIVE_SYNC, evidence)["admitted"])
        failed_v1 = "public-linux-x64-4cpu-prepared-ext4-v1"
        self.assertNotIn(failed_v1, profiles.PROFILES)
        with self.assertRaises(KeyError):
            profiles.admit(failed_v1, synthetic_pair())


if __name__ == "__main__":
    unittest.main()
