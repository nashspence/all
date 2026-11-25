"""Central generic worker qualification; no product imports or time scaling."""
import concurrent.futures as futures
import hashlib
import multiprocessing
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

PROFILE = "public-linux-x64-4cpu-generic/v1"
CAPS_NS = {"cpu_serial": 350_000_000, "cpu_p4": 300_000_000,
           "sha256": 250_000_000, "warm_files": 150_000_000, "fdatasync64": 250_000_000}
CORE_PROBES = ("cpu_serial", "cpu_p4", "sha256", "warm_files")
CPU_EXPECTED = [(0, 1898462336), (1, 1357758593), (2, 817054850), (3, 276351107),
                (4, 4030614660), (5, 3489910917), (6, 2949207174), (7, 2408503431),
                (8, 1867799688), (9, 1327095945), (10, 786392202), (11, 245688459),
                (12, 3999952012), (13, 3459248269), (14, 2918544526), (15, 2377840783)]


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _optional(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _metadata(root):
    mem = _optional("/proc/meminfo") or ""
    cpu = _optional("/proc/cpuinfo") or ""
    total = next((int(s.split()[1]) * 1024 for s in mem.splitlines() if s.startswith("MemTotal:")), None)
    return {"system": platform.system(), "machine": platform.machine(),
            "python": platform.python_version(), "kernel": platform.release(),
            "logical_cpus": os.cpu_count(),
            "affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "memory_total_bytes": total, "free_bytes": shutil.disk_usage(root).free,
            "filesystem": subprocess.check_output(["stat", "-f", "-c", "%T", str(root)], text=True).strip(),
            "cpu_model": next((s.split(":", 1)[1].strip() for s in cpu.splitlines() if s.startswith("model name")), None),
            "cpu_max": _optional("/sys/fs/cgroup/cpu.max"),
            "memory_max": _optional("/sys/fs/cgroup/memory.max"),
            "image_os": os.environ.get("ImageOS"), "image_version": os.environ.get("ImageVersion"),
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def prepare(root):
    """Prepare fixed generic fixtures outside probe timers in a disposable root."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    inputs = root / "central-inputs"
    inputs.mkdir()
    block = bytes(range(256)) * 16
    for index in range(16):
        (inputs / f"{index:02d}.bin").write_bytes(block)
    payload = bytes(range(256)) * 4096
    return {"root": root, "inputs": inputs, "block": block, "payload": payload,
            "expected_hash": hashlib.sha256(payload).hexdigest(), "sync_serial": 0}


def cpu_one(index):
    # Top-level callable remains pickleable when central is imported normally.
    value = index
    for j in range(160000):
        value = (value * 1664525 + 1013904223 + j) & 0xffffffff
    return index, value


def _cpu(workers):
    if workers == 1:
        return [cpu_one(i) for i in range(16)]
    with futures.ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("fork")) as pool:
        return list(pool.map(cpu_one, range(16), chunksize=1))


def _read_files(context):
    observed = []
    for _ in range(256):
        for path in sorted(context["inputs"].iterdir()):
            observed.append((path.name, path.stat().st_size, path.read_bytes()))
    return observed


def _sync_file(context, path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o600)
    writes = 0
    try:
        for _ in range(64):
            remaining = memoryview(context["block"])
            while remaining:
                n = os.write(fd, remaining)
                _require(n > 0, "write made no progress")
                remaining = remaining[n:]
                writes += 1
            os.fdatasync(fd)
    finally:
        os.close(fd)
    return path, writes


def _verify_files(context, observed):
    _require(len(observed) == 4096, "wrong file visit count")
    for index, (name, size, data) in enumerate(observed):
        _require(name == f"{index % 16:02d}.bin" and size == 4096 and data == context["block"], "wrong file result")


def _verify_sync(context, observed):
    path, writes = observed
    try:
        _require(writes >= 64 and path.read_bytes() == context["block"] * 64, "wrong sync output")
    finally:
        path.unlink(missing_ok=True)


def collect(context, repetitions=3):
    """Always collect every generic probe, even when metadata is unsuitable."""
    _require(repetitions == 3, "this fixed profile requires exactly three observations")
    record = {"profile": PROFILE, "metadata": _metadata(context["root"]),
              "samples_ns": {name: [] for name in CAPS_NS}, "errors": {name: [] for name in CAPS_NS}, "order": []}
    cases = {
        "cpu_serial": (lambda: _cpu(1), lambda v: _require(v == CPU_EXPECTED, "wrong CPU result")),
        "cpu_p4": (lambda: _cpu(4), lambda v: _require(v == CPU_EXPECTED, "wrong CPU result")),
        "sha256": (lambda: [hashlib.sha256(context["payload"]).hexdigest() for _ in range(256)],
                   lambda v: _require(v == [context["expected_hash"]] * 256, "wrong hash result")),
        "warm_files": (lambda: _read_files(context), lambda v: _verify_files(context, v)),
    }
    names = list(CAPS_NS)
    for repeat in range(3):
        order = names[repeat:] + names[:repeat]
        for name in order:
            record["order"].append([repeat, name])
            if name == "fdatasync64":
                path = context["root"] / f"central-sync-{context['sync_serial']}.bin"
                context["sync_serial"] += 1
                run, verify = lambda: _sync_file(context, path), lambda v: _verify_sync(context, v)
            else:
                run, verify = cases[name]
            start = time.perf_counter_ns()
            try:
                value = run()
                elapsed = time.perf_counter_ns() - start
            except Exception as error:
                elapsed = time.perf_counter_ns() - start
                record["errors"][name].append({"repeat": repeat, "stage": "execute", "error": type(error).__name__ + ": " + str(error)})
            else:
                try:
                    verify(value)
                except Exception as error:
                    record["errors"][name].append({"repeat": repeat, "stage": "verify", "error": type(error).__name__ + ": " + str(error)})
            record["samples_ns"][name].append(elapsed)
    record["metadata_after"] = _metadata(context["root"])
    record["verified"] = not any(record["errors"].values())
    return record


def evaluate(record):
    """Return independent eligibility decisions; never adjust product timings."""
    core_reasons, sync_reasons = [], []
    if record.get("profile") != PROFILE:
        core_reasons.append("unknown profile")
    for when in ("metadata", "metadata_after"):
        m = record.get(when, {})
        checks = [(m.get("system") == "Linux", "Linux required"),
                  (m.get("machine", "").lower() in ("x86_64", "amd64"), "x64 required"),
                  (m.get("logical_cpus") == 4, "four logical CPUs required"),
                  (m.get("affinity_count") == 4, "affinity to four CPUs required"),
                  (m.get("memory_total_bytes", 0) is not None and m.get("memory_total_bytes", 0) >= 14 * 1024**3, "MemTotal below 14 GiB"),
                  (m.get("free_bytes", 0) >= 512 * 1024**2, "free storage below 512 MiB"),
                  (m.get("filesystem") not in (None, "tmpfs", "ramfs"), "memory filesystem or unknown filesystem")]
        core_reasons.extend(f"{when}: {reason}" for ok, reason in checks if not ok)
    for name, cap in CAPS_NS.items():
        reasons = core_reasons if name in CORE_PROBES else sync_reasons
        values = record.get("samples_ns", {}).get(name, [])
        if len(values) != 3 or any(type(v) is not int or v <= 0 for v in values):
            reasons.append(f"{name}: missing or invalid observations")
        if record.get("errors", {}).get(name):
            reasons.append(f"{name}: execution or verification failure")
        if any(type(v) is int and v > cap for v in values):
            reasons.append(f"{name}: at least one observation exceeds {cap / 1e6:g} ms")
    return {"core_admitted": not core_reasons, "sync_admitted": not core_reasons and not sync_reasons,
            "core_reasons": core_reasons, "sync_reasons": core_reasons + sync_reasons}
