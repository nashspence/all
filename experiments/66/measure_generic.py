"""Fixed #66 storage witnesses using the existing common parent request clock.

CLI: measure_generic.py --root LOOP_A --output NEW_JSON_FILE

The controller owns admission and the external 180-second collection watchdog.
This file neither enrolls a profile nor runs or repeats admission probes. The
eight unchanged storage_cases operations run three times in a fixed rotation.
Each observation uses a new worker and independently prepared fresh fixture;
worker startup, fixture setup, verification/reset and fixture removal are
reported separately. The parent times send(run) through receive(complete).
Every required write/sync/pool shutdown remains in storage_cases.execute.

This file also provides the approved adapter functions loaded by the unchanged
common worker. No elapsed time or pass/fail authority comes from that worker.
Run the CLI in a dedicated process on responsive control storage outside LOOP_A.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True

from all_policy.performance import runner, storage_cases
from all_policy.performance.contracts import Binding
from all_policy.performance.qualify_storage import _checkpoint

SCHEMA = "all-66-generic-storage/1"
REPETITIONS = 3
TIMEOUT_SECONDS = 180
OPERATIONS = (
    "atomic16_p1", "atomic16_p2", "atomic16_p4", "append64_sync",
    "sqlite64_delete_extra", "sqlite64_wal_full",
    "sqlite64_delete_extra_batch", "sqlite64_wal_full_batch",
)
LIMITS_NS = {
    "atomic16_p1": 320_000_000, "atomic16_p2": 320_000_000,
    "atomic16_p4": 320_000_000, "append64_sync": 1_280_000_000,
    "sqlite64_delete_extra": 1_280_000_000, "sqlite64_wal_full": 1_280_000_000,
    "sqlite64_delete_extra_batch": 320_000_000, "sqlite64_wal_full_batch": 320_000_000,
}


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


# Adapter API consumed by the existing all_policy.performance.worker.
def prepare(subject, work):
    work = Path(work)
    spec = json.loads((work / "storage-context.json").read_text())
    _require(set(spec) == {"root", "operation", "repeat"}, "unexpected fixture fields")
    _require(spec["operation"] in OPERATIONS and type(spec["repeat"]) is int
             and 0 <= spec["repeat"] < REPETITIONS, "invalid fixed observation")
    root = Path(spec["root"]).resolve(strict=True)
    _require(root.is_dir(), "existing storage root required")
    fixture = Path(tempfile.mkdtemp(prefix="all-66-generic-", dir=root))
    try:
        context = storage_cases.prepare(fixture / "operation")
    except BaseException:
        shutil.rmtree(fixture)
        raise
    return {"spec": spec, "work": work, "fixture": fixture,
            "context": context, "ran": False, "verified": False}


def run(context, repeat):
    _require(repeat == context["spec"]["repeat"] and not context["ran"],
             "observation cannot be repeated or substituted")
    context["ran"] = True
    return storage_cases.execute(context["context"], context["spec"]["operation"])


def verify(context, receipt, repeat):
    _require(repeat == context["spec"]["repeat"] and context["ran"]
             and not context["verified"], "no fresh completed observation to verify")
    _require(receipt["operation"] == context["spec"]["operation"], "wrong operation receipt")
    # This checks actual bytes/rows and integrity, then resets/removes test output.
    # Every operation sync/acknowledgement has already completed before this call.
    storage_cases.verify(context["context"], receipt)
    (context["work"] / "receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    context["verified"] = True
    return True


def close(context):
    # These are fresh benchmark fixtures, not uncompleted acknowledged writes.
    shutil.rmtree(context["fixture"])


def _empty_observation(repeat):
    return {"repeat": repeat, "elapsed_ns": None, "completed": False,
            "verified": False, "error": "not executed", "stages": {}}


def _decision(row):
    samples = row["observations"]
    valid = len(samples) == REPETITIONS and all(
        s["completed"] is True and s["verified"] is True and s["error"] is None
        and type(s["elapsed_ns"]) is int and s["elapsed_ns"] > 0 for s in samples)
    over = [s["repeat"] for s in samples
            if type(s["elapsed_ns"]) is int and s["elapsed_ns"] > row["limit_ns"]]
    return {"verdict": ("miss" if over else "pass") if valid else "failed",
            "over_limit_repeats": over, "all_three_required": True}


def _observe(binding, subject, root, control, operation, repeat, deadline, sample, publish):
    """Reuse the common fixed protocol and lifecycle; only this parent owns time."""
    worker = None
    stage = "prepare"
    start = None
    sample["error"] = None
    try:
        runner._remaining(deadline)
        runner._check_files(subject, binding)
        with tempfile.TemporaryDirectory(prefix="all-66-control-", dir=control) as directory:
            work = Path(directory)
            (work / "storage-context.json").write_text(json.dumps(
                {"root": str(root), "operation": operation, "repeat": repeat}, sort_keys=True) + "\n")
            try:
                start = time.perf_counter_ns()
                worker = runner._Worker(binding, subject, work, deadline)
                worker.receive("ready")
                sample["stages"]["startup_prepare_ns"] = time.perf_counter_ns() - start
                stage, start = "execute", None
                publish(stage)
                start = time.perf_counter_ns()
                worker.send("run", repeat)
                worker.receive("complete", repeat)
                sample["elapsed_ns"] = time.perf_counter_ns() - start
                sample["completed"] = True
                stage, start = "verify", None
                publish(stage)
                start = time.perf_counter_ns()
                worker.send("verify", repeat)
                worker.receive("verified", repeat)
                sample["stages"]["verification_reset_ns"] = time.perf_counter_ns() - start
                sample["receipt"] = json.loads((work / "receipt.json").read_text())
                sample["verified"] = True
                stage, start = "close", None
                publish(stage)
                start = time.perf_counter_ns()
                worker.send("close")
                worker.receive("closed")
                runner._wait(worker.process, deadline)
                sample["stages"]["drain_fixture_cleanup_ns"] = time.perf_counter_ns() - start
                _require(worker.process.returncode == 0 and not runner._children_remain(worker.process),
                         "generic worker did not finish its complete lifecycle")
            finally:
                if worker is not None:
                    try:
                        worker.log.seek(0)
                        log = worker.log.read(65537)
                        if log:
                            sample["stderr_prefix"] = log[:65536].decode("utf-8", errors="replace")
                            sample["stderr_truncated"] = len(log) > 65536
                    finally:
                        worker.close()
        runner._check_files(subject, binding)
    except Exception as error:
        if stage == "execute" and sample["elapsed_ns"] is None and start is not None:
            sample["elapsed_ns"] = time.perf_counter_ns() - start
        sample["error"] = f"{stage}: {type(error).__name__}: {error}"
    finally:
        publish("observation_complete")


def collect(root, output):
    """All 24 fixed observations, with atomic partial output after each stage.

    Admission and the caller's whole-campaign watchdog are deliberately outside
    this function. The dedicated common process scope owns all worker descendants.
    """
    started = time.perf_counter_ns()
    deadline = time.monotonic() + TIMEOUT_SECONDS
    root, output = Path(root), Path(output)
    source = Path(__file__).resolve()
    subject = source.parents[2]
    relative = str(source.relative_to(subject))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    record = {
        "schema": SCHEMA, "status": "collecting", "complete": False,
        "profile_approved": False, "physical_persistence_proven": False,
        "admission_owned_by": "external frozen campaign controller",
        "root": str(root), "repetitions": REPETITIONS, "payload_bytes": 4096,
        "timeout_seconds": TIMEOUT_SECONDS, "errors": [],
        "coordinator_source_sha256": digest, "shared_source": runner.source_info(),
        "order": [{"repeat": repeat, "operation": operation}
                  for repeat in range(REPETITIONS)
                  for operation in OPERATIONS[repeat:] + OPERATIONS[:repeat]],
        "operations": {operation: {"limit_ns": LIMITS_NS[operation],
            "observations": [_empty_observation(i) for i in range(REPETITIONS)],
            "decision": {"verdict": "failed", "over_limit_repeats": [], "all_three_required": True}}
            for operation in OPERATIONS},
    }
    def progress(stage, operation=None, repeat=None):
        if operation is not None:
            row = record["operations"][operation]
            row["decision"] = _decision(row)
        record["progress"] = {"stage": stage, "operation": operation, "repeat": repeat}
        record["total_ns"] = time.perf_counter_ns() - started
        _checkpoint(output, record)

    binding = Binding(mode="request", unit="one fixed generic storage observation",
                      completion="unchanged execute returned after all writes, syncs and pool shutdown",
                      approved_files=((relative, digest),), adapter=relative)
    try:
        progress("resolve_root")
        root = root.resolve(strict=True)
        _require(root.is_dir(), "existing loop A directory required")
        _require(not output.resolve().is_relative_to(root), "control output must be outside the target root")
        record["resolved_root"] = str(root)
        record["device"] = root.stat().st_dev
        _require(tuple(op for op in storage_cases.OPERATIONS
                       if op not in {"copy16_sync", "sqlite64_delete_full"}) == OPERATIONS,
                 "installed generic operation list differs from the frozen plan")
        with runner._ProcessScope():
            for entry in record["order"]:
                operation, repeat = entry["operation"], entry["repeat"]
                sample = record["operations"][operation]["observations"][repeat]
                progress("observation_start", operation, repeat)
                _observe(binding, subject, root, output.parent, operation, repeat, deadline,
                         sample, lambda stage: progress(stage, operation, repeat))
        _require(hashlib.sha256(source.read_bytes()).hexdigest() == digest,
                 "coordinator source changed during collection")
        _require(runner.source_info() == record["shared_source"],
                 "shared clock/operation source changed during collection")
        _require(root.stat().st_dev == record["device"], "target filesystem identity changed")
        verdicts = {row["decision"]["verdict"] for row in record["operations"].values()}
        record["complete"] = "failed" not in verdicts
        record["status"] = ("complete_with_misses" if "miss" in verdicts else "complete") \
            if record["complete"] else "collection_failed"
    except Exception as error:
        record["errors"].append(type(error).__name__ + ": " + str(error))
        record["status"] = "collection_failed"
        record["complete"] = False
    finally:
        progress("collection_finished")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="The predetermined, externally admitted loop A mount")
    parser.add_argument("--output", required=True, help="New JSON evidence file on responsive control storage")
    args = parser.parse_args(argv)
    # Preserve earlier evidence; target path resolution happens after reservation.
    output = Path(args.output).resolve()
    with output.open("x"):
        pass
    record = collect(Path(os.path.abspath(args.root)), output)
    print(json.dumps({"status": record["status"], "complete": record["complete"],
                      "output": str(output), "profile_approved": False}, sort_keys=True))
    return 0 if record["complete"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
