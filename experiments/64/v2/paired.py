"""Finite experiment: adjacent, independently executed frozen-reference timing.

Not a performance gate, production concurrency feature, or durability proof.
See PLAN.md for the predeclared estimator and acceptance screen.
"""
import argparse
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time

import yaml

BASE = "03de186a044c9c6b365347485a6c4093ce831c79"
REPEATS = 3
MEMBERS = 16
WAIT_NS = 64_000_000
WORKFLOW_PATH = ".github/workflows/all.yml"
MODULES = {}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def command(argv):
    return subprocess.check_output(argv, text=True).strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_protocol(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_one(task):
    role, index, path = task
    return index, MODULES[role].check_repository(path, "nashspence/all")


def checks(role, roots, count, workers):
    tasks = [(role, i % MEMBERS, str(roots[i % MEMBERS])) for i in range(count)]
    if workers == 1:
        return list(map(check_one, tasks))
    # Explicit fork matches Python 3.11's Linux default. Entire pool lifetime is timed.
    with cf.ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork")) as pool:
        return list(pool.map(check_one, tasks, chunksize=1))


def optional_text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def environment(scratch):
    cpu = Path("/proc/cpuinfo").read_text()
    mem = Path("/proc/meminfo").read_text()
    return {
        "python": platform.python_version(), "yaml": yaml.__version__,
        "sqlite": sqlite3.sqlite_version, "machine": platform.machine(),
        "kernel": platform.release(),
        "cpu_model": next((v.split(":", 1)[1].strip() for v in cpu.splitlines() if v.startswith("model name")), None),
        "logical_cpus": os.cpu_count(), "affinity_count": len(os.sched_getaffinity(0)),
        "cpu_max": optional_text("/sys/fs/cgroup/cpu.max"),
        "memory_max": optional_text("/sys/fs/cgroup/memory.max"),
        "memory_total": next((v.split(":", 1)[1].strip() for v in mem.splitlines() if v.startswith("MemTotal")), None),
        "image_os": os.environ.get("ImageOS"), "image_version": os.environ.get("ImageVersion"),
        "filesystem": command(["stat", "-f", "-c", "%T", str(scratch)]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("allocation", type=int)
    parser.add_argument("--smoke", action="store_true", help="Local harness validation, never CI evidence")
    args = parser.parse_args()
    require(1 <= args.allocation <= 24, "unexpected allocation")
    root = Path.cwd()
    frozen = root if args.smoke else root / "calibration-reference"
    if not args.smoke:
        require(command(["git", "rev-parse", "HEAD"]) == os.environ["GITHUB_SHA"], "source mismatch")
        require(command(["git", "-C", str(frozen), "rev-parse", "HEAD"]) == BASE, "reference source mismatch")
        require(command(["git", "diff", "--name-only", BASE, "HEAD", "--", "all_policy", "pyproject.toml", WORKFLOW_PATH]) == "", "production source changed")
        require(sys.version_info[:3] == (3, 11, 9) and yaml.__version__ == "6.0.3", "runtime mismatch")
        require(os.cpu_count() == 4 and len(os.sched_getaffinity(0)) == 4, "wrong public-runner CPU allocation")
    for role, tree in [("reference", frozen), ("candidate", root)]:
        MODULES[role] = load_protocol("_" + role + "_protocol", tree / "all_policy/protocol.py")
    require(digest((frozen / "all_policy/protocol.py").read_bytes()) == digest((root / "all_policy/protocol.py").read_bytes()), "A/A source must be identical")
    fixture = (frozen / WORKFLOW_PATH).read_text()
    pattern = bytes(range(256)) * 16
    variant = pattern[::-1]
    started_ns = time.time_ns()
    with tempfile.TemporaryDirectory(prefix="all-paired-", dir=os.environ.get("RUNNER_TEMP")) as td:
        scratch = Path(td)
        roots, file_roots, fixture_parts = {}, {}, []
        for role in ("reference", "candidate"):
            roots[role] = []
            file_roots[role] = scratch / role / "inputs"
            file_roots[role].mkdir(parents=True)
            for i in range(MEMBERS):
                subject = scratch / role / f"subject-{i:02d}"
                path = subject / WORKFLOW_PATH
                path.parent.mkdir(parents=True)
                text = fixture.replace("name: all\n", f"name: all calibration {i}\n", 1).replace("17 3 * * *", f"{i} 3 * * *", 1)
                path.write_text(text)
                if role == "reference":
                    fixture_parts.append(text.encode())
                roots[role].append(subject)
                (file_roots[role] / f"{i:02d}.bin").write_bytes(pattern)
                require(MODULES[role].check_repository(subject, "nashspence/all") == (), "valid fixture rejected")
            bad = scratch / role / "invalid" / WORKFLOW_PATH
            bad.parent.mkdir(parents=True)
            bad.write_text("name: invalid\non: push\n")
            require(bool(MODULES[role].check_repository(bad.parent.parent.parent, "nashspence/all")), "invalid fixture accepted")

        # Every case has three independently verified reference/candidate pairs.
        # Case tuple: family, candidate modifier; +work retains the same useful result.
        families = [f"policy16_p{p}" for p in (1, 2, 4)]
        families += [f"policy512_p{p}" for p in (1, 2, 4)]
        families += ["files4096", "sqlite64"]
        cases = [(family, mode) for family in families for mode in ("same", "work50")]
        cases += [("policy16_p1", mode) for mode in ("wait_each", "wait_once", "reference_wait_once", "reference_wait_each")]
        cases += [("cycle48", "same"), ("cycle48", "wait_cycle")]
        # Fresh interpreter imports are timed separately; not an all-policy CLI claim.
        cases += [("cold16", "same"), ("cold16", "wait_each")]
        if args.smoke:
            # Same case set and work extents; local data is tagged and cannot qualify CI.
            pass
        samples = {f"{family}/{mode}": {"reference": [], "candidate": []} for family, mode in cases}
        execution_order = []

        def execute(family, role, mode, repeat):
            extra = role == "candidate" and mode == "work50"
            pause = 0
            if role == "candidate" and (mode == "wait_each" or mode == "wait_once" and repeat == 1):
                pause = WAIT_NS
            if role == "reference" and (mode == "reference_wait_each" or mode == "reference_wait_once" and repeat == 1):
                pause = WAIT_NS
            dbpath = scratch / role / f"trial-{family}-{mode}-{repeat}.sqlite"
            require(not dbpath.exists(), "database state leaked")
            start = time.perf_counter_ns()
            if family.startswith("policy"):
                extent, p = family.removeprefix("policy").split("_p")
                count = int(extent)
                # Redundant checks share the same executor lifetime. This is an
                # intentional +50% work dose, not a linear elapsed-time promise.
                all_results = checks(role, roots[role], count + (count // 2 if extra else 0), int(p))
                result, additional = all_results[:count], all_results[count:]
            elif family == "cycle48":
                result = []
                for position in range(3):
                    result += checks(role, roots[role], 16, 1)
                    if role == "candidate" and mode == "wait_cycle" and position == 1:
                        time.sleep(WAIT_NS / 1e9)
                additional = []
            elif family == "files4096":
                n = 384 if extra else 256
                count = nbytes = 0
                checksum = 0
                for _ in range(n):
                    for path in sorted(file_roots[role].iterdir()):
                        size = path.stat().st_size
                        data = path.read_bytes()
                        require(size == 4096 and data == pattern, "input corruption")
                        count += 1
                        nbytes += len(data)
                        checksum += data[1]
                result = (count, nbytes, checksum)
            elif family == "sqlite64":
                db = sqlite3.connect(dbpath)
                try:
                    require(db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete", "journal mode")
                    db.execute("PRAGMA synchronous=FULL")
                    require(db.execute("PRAGMA synchronous").fetchone()[0] == 2, "synchronous mode")
                    db.execute("CREATE TABLE t(i INTEGER PRIMARY KEY,v BLOB)")
                    db.commit()
                    for i in range(64):
                        db.execute("INSERT INTO t VALUES(?,?)", (i, pattern))
                        db.commit()
                    if extra:
                        for i in range(16):
                            for value in (variant, pattern):
                                db.execute("UPDATE t SET v=? WHERE i=?", (value, i))
                                db.commit()
                finally:
                    db.close()
                result = dbpath
            elif family == "cold16":
                source = frozen if role == "reference" else root
                result = subprocess.check_output([sys.executable, str(Path(__file__).resolve()), "--child", str(source / "all_policy/protocol.py"), *map(str, roots[role])], text=True).strip()
            else:
                raise RuntimeError(f"unknown family {family}")
            if pause:
                time.sleep(pause / 1e9)
            elapsed = time.perf_counter_ns() - start
            require(elapsed > 0, "nonpositive duration")
            # Independent checking/reset occurs after complete pool/connection/process shutdown.
            if family.startswith("policy"):
                require(result == [(i % 16, ()) for i in range(count)], "policy output mismatch")
                require(additional == [(i % 16, ()) for i in range(count // 2)] if extra else additional == [], "dose output mismatch")
            elif family == "cycle48":
                require(result == [(i % 16, ()) for i in range(48)], "cycle output mismatch")
            elif family == "files4096":
                require(result == (n * 16, n * 16 * 4096, n * 16), "file result mismatch")
            elif family == "sqlite64":
                with sqlite3.connect(result) as db:
                    require(db.execute("SELECT i,v FROM t ORDER BY i").fetchall() == [(i, pattern) for i in range(64)], "database result mismatch")
                result.unlink()
            elif family == "cold16":
                require(result == "verified:16", "child output mismatch")
            return {"wall_ns": elapsed, "injected_wait_ns": pause + (WAIT_NS if family == "cycle48" and role == "candidate" and mode == "wait_cycle" else 0)}

        for repeat in range(REPEATS):
            offset = (args.allocation - 1 + repeat) % len(cases)
            order = cases[offset:] + cases[:offset]
            if (args.allocation + repeat) % 2 == 0:
                order = order[::-1]
            for case_index, (family, mode) in enumerate(order):
                roles = ["reference", "candidate"]
                if (args.allocation + repeat + case_index) % 2:
                    roles.reverse()
                case = f"{family}/{mode}"
                for role in roles:
                    record = execute(family, role, mode, repeat)
                    samples[case][role].append(record)
                    execution_order.append([repeat, case, role])
        record = {
            "format": "all-paired-calibration/v2", "allocation": args.allocation,
            "phase": "fit" if args.allocation <= 12 else "holdout",
            "source": os.environ.get("GITHUB_SHA", "LOCAL_SMOKE"), "frozen_source": BASE,
            "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "runner_name": os.environ.get("RUNNER_NAME"), "environment": environment(scratch),
            "fixture_sha256": digest(b"\0".join(fixture_parts)),
            "protocol_sha256": digest((frozen / "all_policy/protocol.py").read_bytes()),
            "started_unix_ns": started_ns, "finished_unix_ns": time.time_ns(),
            "samples": samples, "execution_order": execution_order,
            "verified": True, "smoke": args.smoke,
        }
    if not args.smoke:
        require(not command(["git", "status", "--porcelain", "--untracked-files=no"]), "tracked source altered")
    line = json.dumps(record, separators=(",", ":"), sort_keys=True)
    Path("paired-observation.json").write_text(line + "\n")
    print("PAIRED_OBSERVATION " + line, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("## Frozen-reference calibration experiment\n\nAll observations verified; analysis is separate from workflow success.\n\n| Case | Min candidate / min reference |\n|---|---:|\n")
            for case, value in samples.items():
                ratio = min(x["wall_ns"] for x in value["candidate"]) / min(x["wall_ns"] for x in value["reference"])
                f.write(f"| {case} | {ratio:.4f} |\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        module = load_protocol("_cold_protocol", Path(sys.argv[2]))
        result = [module.check_repository(path, "nashspence/all") for path in sys.argv[3:]]
        require(len(result) == 16 and result == [()] * 16, "cold outputs")
        print("verified:16")
    else:
        main()
