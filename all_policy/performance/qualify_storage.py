"""Collect a central, project-independent native-storage qualification packet.

This command does not enroll hardware or approve a shared profile. It refuses
volatile/relaxed mounts, preserves every measurement, and always leaves approval
with shared infrastructure authority. It creates only a disposable directory
beneath the explicit root; it never formats, mounts or reconfigures a device.

The parent enforces one total deadline and atomically checkpoints valid partial
packets. The output directory, installed package and Python runtime must remain
responsive. Use separate healthy control storage when testing storage failures;
a process cannot enforce a deadline while its own control storage is stalled.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import signal
import subprocess
import sys
import tempfile
import time

from . import profiles, storage_cases

SCHEMA = "all-native-storage-qualification/1"
OPERATIONS = tuple(op for op in storage_cases.OPERATIONS
                   if op not in {"copy16_sync", "sqlite64_delete_full"})
CAPS_NS = {op: 100_000_000 if op.startswith("atomic") else 150_000_000 for op in OPERATIONS}
MAX_COLLECTION_SECONDS = 300
MAX_MESSAGE_BYTES = 8 * 1024**2


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


def collect(root, publish=None):
    """Child-only collection; the parent owns timeout and durable packet updates."""
    started = time.perf_counter_ns()
    record = {"schema": SCHEMA, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "root": str(root), "python": platform.python_version(), "hostname": platform.node(),
              "profile_approved": False, "physical_persistence_proven": False,
              "status": "environment_unqualified", "errors": [], "operations": {},
              "shared_source_sha256": {},
              "fixed_probe_caps_ns": CAPS_NS, "repetitions": 3,
              "required_external_evidence": [
                  "shared-authority approval of the actual hardware/filesystem/backing-cache configuration",
                  "fresh repeated allocation/date evidence under the predeclared central validation protocol",
                  "applicable existing product native correctness and failure-model qualification",
                  "a measured real consumer operation meeting its own separately approved raw budget"]}
    def progress(stage, **details):
        record["progress"] = {"stage": stage, **details}
        record["total_ns"] = time.perf_counter_ns() - started
        if publish:
            publish(record)
    try:
        # Even resolving a symlink or inspecting directory access can block on
        # the target filesystem. Keep all target I/O inside the supervised child.
        progress("resolve_root")
        root = Path(root).resolve(strict=True)
        record["resolved_root"] = str(root)
        progress("inspect_root")
        if not root.is_dir() or not os.access(root, os.W_OK):
            raise ValueError("root must be an existing writable directory")
        progress("source_identity")
        record["shared_source_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in Path(__file__).parent.glob("*.py")}
        progress("topology")
        record["topology"] = storage_cases.topology(root)
        record["configuration_reasons"] = configuration_reasons(record["topology"])
        if record["configuration_reasons"]:
            return record
        progress("preflight")
        record["preflight"] = profiles.collect(root)
        record["preflight_admission"] = profiles.admit(profiles.NATIVE_SYNC, record["preflight"])
        if not record["preflight_admission"]["admitted"]:
            return record
        record["status"] = "collecting"
        progress("prepare")
        with tempfile.TemporaryDirectory(prefix="all-native-qualification-", dir=root) as directory:
            record["temporary_directory"] = directory
            record["temporary_cleanup_complete"] = False
            progress("prepare", directory=directory)
            context = storage_cases.prepare(Path(directory) / "operations")
            record["operations"] = {op: {"budget_ns": CAPS_NS[op], "observations": []} for op in OPERATIONS}
            for repeat in range(3):
                for op in OPERATIONS[repeat:] + OPERATIONS[:repeat]:
                    sample = {"elapsed_ns": None, "verified": False, "error": None}
                    record["operations"][op]["observations"].append(sample)
                    progress("execute", operation=op, repeat=repeat)
                    start = time.perf_counter_ns()
                    try:
                        receipt = storage_cases.execute(context, op)
                        sample["elapsed_ns"] = time.perf_counter_ns() - start
                        sample["receipt"] = receipt
                        progress("verify", operation=op, repeat=repeat)
                        storage_cases.verify(context, receipt)
                        sample["verified"] = True
                    except Exception as error:
                        if sample["elapsed_ns"] is None:
                            sample["elapsed_ns"] = time.perf_counter_ns() - start
                        sample["error"] = type(error).__name__ + ": " + str(error)
                    progress("observation_complete", operation=op, repeat=repeat)
            for row in record["operations"].values():
                values = row["observations"]
                valid = len(values) == 3 and all(s["verified"] and not s["error"] for s in values)
                row["screen"] = ("pass" if all(s["elapsed_ns"] <= row["budget_ns"] for s in values)
                                 else "miss") if valid else "failed"
            progress("postflight")
            record["postflight"] = profiles.collect(root)
            progress("topology_after")
            record["topology_after"] = storage_cases.topology(root)
            progress("cleanup")
        record["temporary_cleanup_complete"] = True
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


def _worker(root):
    def publish(record, complete=False):
        print(json.dumps({"record": record, "complete": complete}, separators=(",", ":")), flush=True)
    record = collect(Path(root), publish)
    publish(record, complete=True)


def _child_command(root):
    # Pin imports to this installed package, even when the caller's cwd contains
    # another all_policy tree. Isolated mode also ignores PYTHONPATH.
    package_parent = str(Path(__file__).resolve().parents[2])
    bootstrap = ("import sys; sys.path.insert(0, sys.argv[1]); "
                 "from all_policy.performance.qualify_storage import _worker; _worker(sys.argv[2])")
    return [sys.executable, "-I", "-B", "-c", bootstrap, package_parent, str(root)]


def _checkpoint(output, record):
    """Atomic replacement preserves the last valid JSON if the writer stops."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=output.parent,
                                         prefix=output.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class _Interrupted(Exception):
    pass


def _collect_bounded(root, output, timeout_seconds):
    started = time.monotonic()
    deadline = started + timeout_seconds
    record = {"schema": SCHEMA, "root": str(root), "profile_approved": False,
              "physical_persistence_proven": False, "status": "collecting",
              "errors": [], "operations": {}, "progress": {"stage": "worker_start"}}
    coordinator = {"deadline_seconds": timeout_seconds, "complete": False,
                   "timed_out": False, "snapshots_received": 0,
                   "control_storage_requirement": "responsive output directory, package and runtime"}
    def check_deadline():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            coordinator["timed_out"] = True
            raise TimeoutError(f"total collection deadline of {timeout_seconds:g}s exceeded")
        return remaining
    record["coordinator"] = coordinator
    _checkpoint(output, record)
    process, complete, buffer, stderr = None, False, bytearray(), bytearray()
    selector = selectors.DefaultSelector()
    def interrupted(signum, frame):
        raise _Interrupted(f"received signal {signum}")
    previous_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        process = subprocess.Popen(_child_command(root), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, bufsize=0, start_new_session=True)
        coordinator["worker_pid"] = process.pid
        for stream, kind in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, kind)
        while selector.get_map() or process.poll() is None:
            remaining = check_deadline()
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == "stderr":
                    stderr.extend(chunk[:max(0, 16384 - len(stderr))])
                    continue
                buffer.extend(chunk)
                if len(buffer) > MAX_MESSAGE_BYTES:
                    raise RuntimeError("qualification worker message exceeds fixed size limit")
                while b"\n" in buffer:
                    check_deadline()
                    line, _, remainder = buffer.partition(b"\n")
                    buffer = bytearray(remainder)
                    packet = json.loads(line)
                    incoming = packet["record"]
                    if (incoming.get("schema") != SCHEMA or incoming.get("root") != str(root) or
                            incoming.get("profile_approved") is not False or
                            incoming.get("physical_persistence_proven") is not False):
                        raise RuntimeError("invalid qualification worker packet")
                    record = incoming
                    record["coordinator"] = coordinator
                    coordinator["snapshots_received"] += 1
                    complete = packet.get("complete") is True
                    _checkpoint(output, record)
        check_deadline()
        if buffer or not complete or process.returncode != 0:
            raise RuntimeError(f"qualification worker exited incompletely (exit {process.returncode})")
        coordinator["complete"] = True
    except (Exception, KeyboardInterrupt) as error:
        failure = type(error).__name__ + ": " + str(error)
        record["errors"].append(failure)
        record["status"] = "collection_failed"
        progress = record.get("progress", {})
        operation = record.get("operations", {}).get(progress.get("operation"), {})
        observations = operation.get("observations", [])
        if progress.get("stage") in {"execute", "verify"} and observations:
            sample = observations[-1]
            if not sample.get("verified") and sample.get("error") is None:
                sample["error"] = failure
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        if process is not None:
            if not coordinator["complete"]:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    coordinator["termination_requested"] = True
                except ProcessLookupError:
                    pass
                # A task blocked in kernel I/O need not exit promptly even after
                # SIGKILL. Never join it without a short explicit bound.
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    coordinator["termination_unconfirmed"] = True
            coordinator["worker_returncode"] = process.poll()
            for stream in (process.stdout, process.stderr):
                stream.close()
        selector.close()
        coordinator["elapsed_ns"] = int((time.monotonic() - started) * 1e9)
        if stderr:
            coordinator["stderr_prefix"] = stderr.decode("utf-8", errors="replace")
        record["coordinator"] = coordinator
        _checkpoint(output, record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Actual native filesystem used by the intended operation")
    parser.add_argument("--output", required=True, help="New evidence file on responsive control storage; existing evidence is never replaced")
    parser.add_argument("--timeout-seconds", type=float, default=MAX_COLLECTION_SECONDS,
                        help="Total collection deadline, positive and at most 300 seconds")
    args = parser.parse_args(argv)
    # abspath is lexical: do not stat or resolve the target before supervision.
    root = Path(os.path.abspath(args.root))
    if not 0 < args.timeout_seconds <= MAX_COLLECTION_SECONDS:
        parser.error("timeout must be positive and at most 300 seconds")
    # Reserve the destination before touching the test root, preserving previous evidence.
    output = Path(args.output).resolve()
    try:
        with output.open("x"):
            pass
        record = _collect_bounded(root, output, args.timeout_seconds)
    except OSError as error:
        print(json.dumps({"status": "collection_failed", "error": str(error), "profile_approved": False}), file=sys.stderr)
        return 3
    print(json.dumps({"status": record["status"], "profile_approved": False,
                      "evidence": str(Path(args.output).resolve())}))
    # Qualification packets are not an accepted product gate or automatic enrollment.
    return 3 if record["status"] == "collection_failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
