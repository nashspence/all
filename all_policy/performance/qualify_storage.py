"""Collect a central, project-independent native-storage qualification packet.

This command does not enroll hardware or approve a shared profile. It refuses
volatile/relaxed mounts, preserves every measurement, and always leaves approval
with shared infrastructure authority. It creates only a disposable directory
beneath the explicit root; it never formats, mounts or reconfigures a device.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time

from . import profiles, storage_cases

SCHEMA = "all-native-storage-qualification/1"
OPERATIONS = tuple(op for op in storage_cases.OPERATIONS
                   if op not in {"copy16_sync", "sqlite64_delete_full"})
CAPS_NS = {op: 100_000_000 if op.startswith("atomic") else 150_000_000 for op in OPERATIONS}


def configuration_reasons(topology):
    reasons = []
    if topology.get("filesystem") not in {"ext4", "xfs"}:
        reasons.append("first native qualification requires an observed ext4 or xfs filesystem")
    options = set(topology.get("mount_options", []))
    rejected = options & profiles.UNSAFE_DURABILITY_OPTIONS
    if rejected:
        reasons.append("relaxed mount settings are outside this proposed native profile: " + ", ".join(sorted(rejected)))
    mount = topology.get("mount", {}).get("data", {}).get("filesystems", [])
    if not mount or not mount[0].get("source") or not topology.get("device"):
        reasons.append("actual mount source/device evidence is missing")
    if topology.get("loop_backing") is not None:
        reasons.append("loop backing requires separately approved whole-stack storage qualification")
    if "ro" in options or "rw" not in options:
        reasons.append("writable mount evidence required")
    return reasons


def collect(root):
    started = time.perf_counter_ns()
    record = {"schema": SCHEMA, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "root": str(root), "python": platform.python_version(), "hostname": platform.node(),
              "profile_approved": False, "physical_persistence_proven": False,
              "status": "environment_unqualified", "errors": [], "operations": {},
              "shared_source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in Path(__file__).parent.glob("*.py")},
              "fixed_probe_caps_ns": CAPS_NS, "repetitions": 3,
              "required_external_evidence": [
                  "shared-authority approval of the actual hardware/filesystem/backing-cache configuration",
                  "fresh repeated allocation/date evidence under the predeclared central validation protocol",
                  "applicable existing product native correctness and failure-model qualification",
                  "a measured real consumer operation meeting its own separately approved raw budget"]}
    try:
        record["topology"] = storage_cases.topology(root)
        record["configuration_reasons"] = configuration_reasons(record["topology"])
        if record["configuration_reasons"]:
            return record
        record["preflight"] = profiles.collect(root)
        record["preflight_admission"] = profiles.admit(profiles.NATIVE_SYNC, record["preflight"])
        if not record["preflight_admission"]["admitted"]:
            return record
        record["status"] = "collecting"
        with tempfile.TemporaryDirectory(prefix="all-native-qualification-", dir=root) as directory:
            context = storage_cases.prepare(Path(directory) / "operations")
            record["operations"] = {op: {"budget_ns": CAPS_NS[op], "observations": []} for op in OPERATIONS}
            for repeat in range(3):
                for op in OPERATIONS[repeat:] + OPERATIONS[:repeat]:
                    sample = {"elapsed_ns": None, "verified": False, "error": None}
                    record["operations"][op]["observations"].append(sample)
                    start = time.perf_counter_ns()
                    try:
                        receipt = storage_cases.execute(context, op)
                        sample["elapsed_ns"] = time.perf_counter_ns() - start
                        sample["receipt"] = receipt
                        storage_cases.verify(context, receipt)
                        sample["verified"] = True
                    except Exception as error:
                        if sample["elapsed_ns"] is None:
                            sample["elapsed_ns"] = time.perf_counter_ns() - start
                        sample["error"] = type(error).__name__ + ": " + str(error)
            for row in record["operations"].values():
                values = row["observations"]
                valid = len(values) == 3 and all(s["verified"] and not s["error"] for s in values)
                row["screen"] = ("pass" if all(s["elapsed_ns"] <= row["budget_ns"] for s in values)
                                 else "miss") if valid else "failed"
            record["postflight"] = profiles.collect(root)
            record["topology_after"] = storage_cases.topology(root)
        record["postflight_cannot_erase_misses"] = True
        record["configuration_reasons_after"] = configuration_reasons(record["topology_after"])
        record["storage_configuration_changed"] = any(
            record["topology"].get(key) != record["topology_after"].get(key)
            for key in ("device", "filesystem", "mount_options"))
        record["status"] = ("screen_pass_pending_shared_review"
                            if all(v["screen"] == "pass" for v in record["operations"].values())
                            and not record["configuration_reasons_after"]
                            and not record["storage_configuration_changed"]
                            else "screen_failed")
    except Exception as error:
        record["errors"].append(type(error).__name__ + ": " + str(error))
        record["status"] = "collection_failed"
    finally:
        record["total_ns"] = time.perf_counter_ns() - started
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Actual native filesystem used by the intended operation")
    parser.add_argument("--output", required=True, help="New evidence file; existing files are never replaced")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir() or not os.access(root, os.W_OK):
        parser.error("root must be an existing writable directory")
    # Reserve the destination before touching the test root, preserving previous evidence.
    with Path(args.output).open("x") as destination:
        record = collect(root)
        json.dump(record, destination, sort_keys=True, indent=2)
        destination.write("\n")
    print(json.dumps({"status": record["status"], "profile_approved": False,
                      "evidence": str(Path(args.output).resolve())}))
    # Qualification packets are not an accepted product gate or automatic enrollment.
    return 3 if record["status"] == "collection_failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
