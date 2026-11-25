"""Generic admission only: no candidate imports, time division or budget scaling.

Filesystem API timing and persistence qualification are different claims. Even a
native mount which accepts fsync is not thereby certified to survive power loss.
"""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from types import MappingProxyType


@dataclass(frozen=True)
class Profile:
    storage: str
    sync: bool
    claim: str


CORE = "public-linux-x64-4cpu-native-api-v1"
NATIVE_SYNC = "public-linux-x64-4cpu-native-sync-api-v1"
VOLATILE_SYNC = "public-linux-x64-4cpu-volatile-memory-v1"
DURABLE = "linux-x64-4cpu-qualified-durable-v1"
PROFILES = MappingProxyType({
    CORE: Profile("native", False, "CPU and native filesystem API latency; no persistence qualification"),
    NATIVE_SYNC: Profile("native", True, "Native synchronization API latency; no persistence qualification"),
    VOLATILE_SYNC: Profile("volatile", True, "Software and synchronization-call latency on volatile tmpfs; no persistence"),
    DURABLE: Profile("durable", True, "Reserved: requires approved infrastructure-specific durability qualification"),
})
CAPS_NS = MappingProxyType({"cpu_serial": 350_000_000, "cpu_p4": 300_000_000,
                           "sha256": 250_000_000, "warm_files": 150_000_000,
                           "fdatasync64": 250_000_000})
UNSAFE_DURABILITY_OPTIONS = {"nobarrier", "barrier=0", "data=writeback", "journal_async_commit"}
CPU_EXPECTED = [1898462336, 1357758593, 817054850, 276351107, 4030614660, 3489910917,
                2949207174, 2408503431, 1867799688, 1327095945, 786392202, 245688459,
                3999952012, 3459248269, 2918544526, 2377840783]


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _json_command(arguments):
    return json.loads(subprocess.check_output(arguments, text=True, timeout=10,
                                              stderr=subprocess.DEVNULL))


def metadata(root):
    """Observe actual target mount/options and block topology, never infer from label."""
    mem = _read("/proc/meminfo") or ""
    cpu = _read("/proc/cpuinfo") or ""
    result = {"system": platform.system(), "machine": platform.machine(),
            "python": platform.python_version(), "logical_cpus": os.cpu_count(),
            "affinity_count": len(os.sched_getaffinity(0)),
            "cpu_model": next((s.split(":", 1)[1].strip() for s in cpu.splitlines()
                               if s.startswith("model name")), None),
            "memory_total_bytes": next((int(s.split()[1]) * 1024 for s in mem.splitlines()
                                        if s.startswith("MemTotal:")), None),
            "memory_max": _read("/sys/fs/cgroup/memory.max"),
            "cpu_max": _read("/sys/fs/cgroup/cpu.max"),
            "free_bytes": shutil.disk_usage(root).free, "root": str(Path(root).resolve()),
            "device": os.stat(root).st_dev,
            "image_os": os.environ.get("ImageOS"), "image_version": os.environ.get("ImageVersion")}
    try:
        result["mount"] = _json_command(["findmnt", "--json", "--target", str(root), "--output",
                                         "TARGET,SOURCE,FSTYPE,OPTIONS,MAJ:MIN"])["filesystems"][0]
    except Exception as error:
        result["mount_error"] = str(error)
    try:
        result["topology"] = _json_command(["lsblk", "--json", "--output",
                                            "KNAME,TYPE,PKNAME,MAJ:MIN,MODEL,ROTA,TRAN"])
    except Exception as error:
        result["topology_error"] = str(error)
    return result


def _cpu(index):
    value = index
    for j in range(160000):
        value = (value * 1664525 + 1013904223 + j) & 0xffffffff
    return value


def _cpu_p4():
    with ProcessPoolExecutor(4, mp_context=multiprocessing.get_context("fork")) as pool:
        return list(pool.map(_cpu, range(16), chunksize=1))


def collect(root):
    """One fixed five-probe, three-observation preflight per actual storage root."""
    root = Path(root).resolve()
    record = {"samples_ns": {name: [] for name in CAPS_NS}, "errors": [], "metadata": {}}
    try:
        record["metadata"] = metadata(root)
        with tempfile.TemporaryDirectory(prefix="all-profile-", dir=root) as directory:
            scratch = Path(directory)
            block, payload = bytes(range(256)) * 16, bytes(range(256)) * 4096
            inputs = [scratch / f"input-{i:02d}" for i in range(16)]
            for path in inputs:
                path.write_bytes(block)

            def reads():
                return [(p.name, p.stat().st_size, p.read_bytes()) for _ in range(256)
                        for p in sorted(scratch.glob("input-*"))]

            def syncs():
                path = scratch / "sync-output"
                path.unlink(missing_ok=True)
                with path.open("wb", buffering=0) as stream:
                    for _ in range(64):
                        if stream.write(block) != len(block):
                            raise RuntimeError("short probe write")
                        os.fdatasync(stream.fileno())
                return path

            expected_reads = [(p.name, len(block), block) for _ in range(256) for p in inputs]
            expected_hashes = [hashlib.sha256(payload).digest()] * 256
            cases = {
                "cpu_serial": (lambda: [_cpu(i) for i in range(16)], lambda v: v == CPU_EXPECTED),
                "cpu_p4": (_cpu_p4, lambda v: v == CPU_EXPECTED),
                "sha256": (lambda: [hashlib.sha256(payload).digest() for _ in range(256)],
                           lambda v: v == expected_hashes),
                "warm_files": (reads, lambda v: v == expected_reads),
                "fdatasync64": (syncs, lambda v: v.read_bytes() == block * 64),
            }
            names = list(cases)
            for repeat in range(3):
                for name in names[repeat:] + names[:repeat]:
                    run, verify = cases[name]
                    start = time.perf_counter_ns()
                    try:
                        value = run()
                        elapsed = time.perf_counter_ns() - start
                        if not verify(value):
                            raise RuntimeError("probe output mismatch")
                    except Exception as error:
                        elapsed = time.perf_counter_ns() - start
                        record["errors"].append({"probe": name, "repeat": repeat,
                                                 "error": str(error)})
                    record["samples_ns"][name].append(elapsed)
            record["metadata_after"] = metadata(root)
    except Exception as error:
        record["errors"].append({"probe": "metadata", "error": str(error)})
    return record


def admit(profile_id, evidence):
    """Reject incompatible or impaired environments without adjusting any budget."""
    profile, reasons = PROFILES[profile_id], []
    if profile.storage == "durable":
        reasons.append("no infrastructure-specific durability qualification is registered")
    for when in ("metadata", "metadata_after"):
        row = evidence.get(when, {})
        mount = row.get("mount", {})
        checks = [
            (row.get("system") == "Linux", "Linux required"),
            (row.get("machine", "").lower() in {"x86_64", "amd64"}, "x64 required"),
            (row.get("python") == "3.11.9", "shared probe runtime Python 3.11.9 required"),
            (row.get("logical_cpus") == 4 and row.get("affinity_count") == 4, "four available CPUs required"),
            (isinstance(row.get("memory_total_bytes"), int) and row["memory_total_bytes"] >= 14 * 1024**3,
             "14 GiB memory required"),
            (row.get("free_bytes", 0) >= 64 * 1024**2, "64 MiB scratch capacity required"),
            (mount.get("fstype") == "tmpfs" if profile.storage == "volatile"
             else mount.get("fstype") in {"ext4", "xfs", "btrfs"}, "incompatible storage semantics"),
            (bool(mount.get("source")) and bool(mount.get("options")),
             "mount options/source evidence required"),
            (profile.storage == "volatile" or bool(row.get("topology")),
             "native block topology evidence required"),
        ]
        quota = row.get("cpu_max")
        if isinstance(quota, str) and not quota.startswith("max "):
            try:
                amount, period = map(int, quota.split())
                checks.append((period > 0 and amount >= 4 * period, "CPU quota below four CPUs"))
            except ValueError:
                checks.append((False, "invalid CPU quota"))
        memory_max = row.get("memory_max")
        if memory_max not in (None, "max"):
            checks.append((str(memory_max).isdigit() and int(memory_max) >= 14 * 1024**3,
                           "memory quota below 14 GiB"))
        if profile.storage == "durable":
            options = set(mount.get("options", "").split(","))
            checks.append((not options & UNSAFE_DURABILITY_OPTIONS, "unsafe durability mount option"))
        reasons.extend(f"{when}: {message}" for ok, message in checks if not ok)
    before, after = evidence.get("metadata", {}), evidence.get("metadata_after", {})
    if any(before.get(k) != after.get(k) for k in ("root", "device", "mount")):
        reasons.append("storage location or mount changed during preflight")
    for name, cap in CAPS_NS.items():
        if name == "fdatasync64" and not profile.sync:
            continue
        samples = evidence.get("samples_ns", {}).get(name, [])
        if len(samples) != 3 or any(type(n) is not int or n <= 0 or n > cap for n in samples):
            reasons.append(f"{name}: missing, invalid or over-cap observation")
        if any(e.get("probe") in {name, "metadata"} for e in evidence.get("errors", [])):
            reasons.append(f"{name}: probe failed")
    return {"profile": profile_id, "admitted": not reasons, "reasons": reasons,
            "claim": profile.claim, "persistence_qualified": False}


if __name__ == "__main__":
    print(json.dumps(collect(sys.argv[1])))
