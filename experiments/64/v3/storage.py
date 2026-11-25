"""Bounded SQLite completion-window calibration; not physical durability proof."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time

WINDOWS = (64, 256, 1024)
REPEATS = 3
PAYLOAD = bytes(range(256)) * 16
VARIANT = PAYLOAD[::-1]


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def command(args):
    return subprocess.check_output(args, text=True).strip()


def read_optional(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def execute(path, extent, extra, deadline):
    require(not path.exists(), "database state leaked")
    start = time.perf_counter_ns()
    db = None
    commits = 0
    schema_commits = 0
    failure = None
    try:
        db = sqlite3.connect(path)
        require(db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete", "journal mode")
        db.execute("PRAGMA synchronous=FULL")
        require(db.execute("PRAGMA synchronous").fetchone()[0] == 2, "synchronous mode")
        db.execute("CREATE TABLE t(i INTEGER PRIMARY KEY,v BLOB)")
        db.commit()
        schema_commits = 1
        # Every operation commits; no batching or durability setting changes.
        for i in range(extent):
            require(time.monotonic() < deadline, "collection deadline exceeded")
            db.execute("INSERT INTO t VALUES(?,?)", (i, PAYLOAD))
            db.commit()
            commits += 1
        if extra:
            for i in range(extent // 4):
                for value in (VARIANT, PAYLOAD):
                    require(time.monotonic() < deadline, "collection deadline exceeded")
                    db.execute("UPDATE t SET v=? WHERE i=?", (value, i))
                    db.commit()
                    commits += 1
    except Exception as exc:
        failure = type(exc).__name__ + ": " + str(exc)
    finally:
        if db is not None:
            db.close()
    wall_ns = time.perf_counter_ns() - start
    verified = False
    if failure is None:
        try:
            check = sqlite3.connect(path)
            try:
                require(check.execute("SELECT i,v FROM t ORDER BY i").fetchall() == [(i, PAYLOAD) for i in range(extent)], "final rows differ")
                require(check.execute("PRAGMA integrity_check").fetchone() == ("ok",), "integrity check")
            finally:
                check.close()
            require(commits == extent + (extent // 2 if extra else 0), "commit count")
            verified = True
        except Exception as exc:
            failure = type(exc).__name__ + ": " + str(exc)
    path.unlink(missing_ok=True)
    return {"wall_ns": wall_ns, "data_commits": commits, "schema_commits": schema_commits,
            "verified": verified, "error": failure}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("allocation", type=int)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    require(1 <= args.allocation <= 12, "allocation must be 1..12")
    if not args.smoke:
        require(command(["git", "rev-parse", "HEAD"]) == os.environ["GITHUB_SHA"], "source mismatch")
        require(sys.version_info[:3] == (3, 11, 9), "runtime mismatch")
        require(os.cpu_count() == 4 and len(os.sched_getaffinity(0)) == 4, "CPU allocation mismatch")
    started = time.monotonic()
    deadline = started + 90
    cpu = read_optional("/proc/cpuinfo") or ""
    record = {
        "format": "all-storage-calibration/v3", "allocation": args.allocation,
        "phase": "fit" if args.allocation <= 6 else "holdout", "smoke": args.smoke,
        "source": os.environ.get("GITHUB_SHA", "LOCAL_SMOKE"),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(PAYLOAD + VARIANT).hexdigest(),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "runner_name": os.environ.get("RUNNER_NAME"), "started_unix_ns": time.time_ns(),
        "environment": {
            "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "machine": platform.machine(), "kernel": platform.release(),
            "cpu_model": next((x.split(":", 1)[1].strip() for x in cpu.splitlines() if x.startswith("model name")), None),
            "logical_cpus": os.cpu_count(), "affinity_count": len(os.sched_getaffinity(0)),
            "cpu_max": read_optional("/sys/fs/cgroup/cpu.max"),
            "memory_max": read_optional("/sys/fs/cgroup/memory.max"),
            "image_os": os.environ.get("ImageOS"), "image_version": os.environ.get("ImageVersion"),
        }, "samples": {}, "execution_order": [], "complete": False,
    }
    cases = [(n, mode) for n in WINDOWS for mode in ("same", "work50")]
    for n, mode in cases:
        record["samples"][f"sqlite{n}/{mode}"] = {role: [] for role in ("reference", "candidate", "guard")}
    with tempfile.TemporaryDirectory(prefix="all-storage-", dir=os.environ.get("RUNNER_TEMP")) as td:
        root = Path(td)
        record["environment"]["filesystem"] = command(["stat", "-f", "-c", "%T", str(root)])
        failed = False
        for repeat in range(REPEATS):
            offset = (args.allocation + repeat - 1) % len(cases)
            order = cases[offset:] + cases[:offset]
            if (args.allocation + repeat) % 2 == 0:
                order.reverse()
            for case_index, (n, mode) in enumerate(order):
                case = f"sqlite{n}/{mode}"
                roles = ["reference", "candidate", "guard"]
                if (args.allocation + repeat + case_index) % 2:
                    roles.reverse()
                for role in roles:
                    sample = execute(root / f"{case.replace('/', '-')}-{repeat}-{role}.sqlite", n,
                                     role == "candidate" and mode == "work50", deadline)
                    record["samples"][case][role].append(sample)
                    record["execution_order"].append([repeat, case, role])
                    if not sample["verified"]:
                        failed = True
                        break
                if failed:
                    break
            if failed:
                break
        record["complete"] = not failed
    record["finished_unix_ns"] = time.time_ns()
    record["elapsed_ns"] = round((time.monotonic() - started) * 1e9)
    line = json.dumps(record, separators=(",", ":"), sort_keys=True)
    Path("storage-observation.json").write_text(line + "\n")
    print("STORAGE_OBSERVATION " + line, flush=True)
    return 0 if record["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
