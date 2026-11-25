"""Finite #64 pilot. No product performance gate; frozen reference checkout."""
import concurrent.futures as cf
import hashlib
import json
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
from all_policy.protocol import check_repository, SOURCE_REPOSITORY, WORKFLOW_PATH

BASE = "03de186a044c9c6b365347485a6c4093ce831c79"
MEMBERS = 16
BATCHES = 32
REPEATS = 3
WORKERS = (1, 2, 4)

def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def cpu_one(i):
    value = i
    for j in range(160000):
        value = (value * 1664525 + 1013904223 + j) & 0xffffffff
    return i, value

def check_one(pair):
    i, path = pair
    return i, check_repository(path, SOURCE_REPOSITORY)

def map_tasks(fn, tasks, p):
    if p == 1:
        return list(map(fn, tasks))
    # New pool and full receiving for each observation, not retained between repeats.
    with cf.ProcessPoolExecutor(max_workers=p) as pool:
        return list(pool.map(fn, tasks, chunksize=1))

def measure(fn, verify):
    start = time.perf_counter_ns()
    value = fn()
    elapsed = time.perf_counter_ns() - start
    verify(value)
    require(elapsed > 0, "nonpositive elapsed")
    return elapsed

def main():
    allocation = int(sys.argv[1])
    require(1 <= allocation <= 24, "unexpected allocation")
    require(out(["git","rev-parse","HEAD"]) == os.environ["GITHUB_SHA"], "source mismatch")
    require(out(["git","diff","--name-only",BASE,"HEAD","--","all_policy","pyproject.toml",".github/workflows/all.yml"]) == "", "frozen production files changed")
    require(not out(["git","status","--porcelain","--untracked-files=no"]), "tracked changes")
    require(sys.version_info[:3] == (3,11,9) and yaml.__version__ == "6.0.3", "runtime mismatch")
    root = Path.cwd()
    fixture = (root / WORKFLOW_PATH).read_text(encoding="utf-8")
    expected_cpu = [cpu_one(i) for i in range(MEMBERS)]
    cases = {}
    with tempfile.TemporaryDirectory(prefix="all-calibration-",dir=os.environ["RUNNER_TEMP"]) as tmp:
        scratch = Path(tmp)
        inputs = scratch / "files"; inputs.mkdir()
        pattern = bytes(range(256))*16
        paths = []
        for i in range(MEMBERS):
            path = inputs / f"{i:02d}.bin"
            path.write_bytes(pattern); paths.append(path)
        roots = []
        source_parts = []
        for i in range(MEMBERS):
            subject = scratch / f"subject-{i:02d}"
            workflow = subject / WORKFLOW_PATH
            workflow.parent.mkdir(parents=True)
            text = fixture.replace("name: all\n",f"name: all calibration {i}\n",1).replace("17 3 * * *",f"{i} 3 * * *",1)
            require(text != fixture,"fixture variation failed")
            workflow.write_text(text,encoding="utf-8")
            source_parts.append(text.encode())
            roots.append((i,str(subject)))
        # Complete independent expected results: every real subject must pass.
        expected = [(i,()) for i in range(MEMBERS)] * BATCHES
        require(all(check_one(x)==(x[0],()) for x in roots),"valid fixtures rejected")
        bad = scratch/"invalid"; bad_file=bad/WORKFLOW_PATH; bad_file.parent.mkdir(parents=True)
        bad_file.write_text("name: invalid\non: push\n",encoding="utf-8")
        require(bool(check_repository(bad,SOURCE_REPOSITORY)), "negative control accepted")
        def assert_equal(actual, want):
            require(actual == want, "verification mismatch")
        def read_files():
            count = nbytes = 0
            for _ in range(256):
                for path in sorted(inputs.iterdir()):
                    require(path.stat().st_size==4096, "file extent changed")
                    data = path.read_bytes()
                    require(data == pattern, "file contents changed")
                    count += 1; nbytes += len(data)
            return count,nbytes
        cases["files_warm"] = (read_files, lambda v: assert_equal(v,(4096,16777216)))
        # Fixed standard-library hash work, independent of production code.
        payload = bytes(range(256))*4096
        h = digest(payload)
        def hash_work():
            return [digest(payload) for _ in range(256)]
        cases["sha256"] = (hash_work, lambda v: assert_equal(v,[h]*256))
        def sqlite_trial():
            dbpath = scratch/"sync.sqlite"
            require(not dbpath.exists(),"unclean SQLite reset")
            db=sqlite3.connect(dbpath)
            try:
                require(db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]=="delete","wrong journal mode")
                db.execute("PRAGMA synchronous=FULL")
                require(db.execute("PRAGMA synchronous").fetchone()[0]==2,"wrong sync setting")
                db.execute("CREATE TABLE t(i INTEGER PRIMARY KEY,v BLOB)");db.commit()
                for i in range(64):
                    db.execute("INSERT INTO t VALUES(?,?)",(i,pattern)); db.commit()
            finally:
                db.close()
            return dbpath
        def verify_db(path):
            with sqlite3.connect(path) as db:
                require(db.execute("SELECT i,v FROM t ORDER BY i").fetchall()==[(i,pattern) for i in range(64)],"SQLite contents")
            # Verification and reset are outside this control's measured create/commit/close interval.
            path.unlink()
        cases["sqlite_full"]=(sqlite_trial,verify_db)
        for p in WORKERS:
            cases[f"cpu_p{p}"]=(lambda p=p:map_tasks(cpu_one,list(range(MEMBERS)),p),
                                 lambda v:assert_equal(v,expected_cpu))
            cases[f"policy_p{p}"]=(lambda p=p:map_tasks(check_one,roots*BATCHES,p),
                                    lambda v:assert_equal(v,expected))
        # Counterbalance order across independent allocations and repeated trials.
        names=list(cases)
        values={n:[] for n in names}
        orders=[]
        for repeat in range(REPEATS):
            offset=(allocation-1+repeat)%len(names)
            order=names[offset:]+names[:offset]
            if (allocation+repeat)%2==0:
                order=order[::-1]
            orders.append(order)
            for name in order:
                values[name].append(measure(*cases[name]))
        def read_optional(path):
            try: return Path(path).read_text().strip()
            except OSError: return None
        model=next((x.split(":",1)[1].strip() for x in Path("/proc/cpuinfo").read_text().splitlines() if x.startswith("model name")),None)
        mem=next((x.split(":",1)[1].strip() for x in Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemTotal")),None)
        record={
          "format":"all-calibration-pilot/v1","allocation":allocation,"source":os.environ["GITHUB_SHA"],"frozen_source":BASE,
          "run_id":os.environ["GITHUB_RUN_ID"],"run_attempt":os.environ["GITHUB_RUN_ATTEMPT"],
          "python":platform.python_version(),"yaml":yaml.__version__,"sqlite":sqlite3.sqlite_version,
          "machine":platform.machine(),"kernel":platform.release(),"cpu_model":model,
          "logical_cpus":os.cpu_count(),"affinity_count":len(os.sched_getaffinity(0)),
          "cpu_max":read_optional("/sys/fs/cgroup/cpu.max"),"memory_max":read_optional("/sys/fs/cgroup/memory.max"),
          "memory_total":mem,"image_os":os.environ.get("ImageOS"),"image_version":os.environ.get("ImageVersion"),
          "filesystem":out(["stat","-f","-c","%T",str(scratch)]),
          "members":MEMBERS,"batches":BATCHES,"fixture_sha256":digest(b"\0".join(source_parts)),
          "order":orders,"samples_ns":values,"verified":True,
        }
    require(not out(["git","status","--porcelain","--untracked-files=no"]), "tracked changes after run")
    line=json.dumps(record,sort_keys=True,separators=(",",":"))
    Path("calibration-observation.json").write_text(line+"\n",encoding="utf-8")
    print("CALIBRATION_OBSERVATION "+line,flush=True)
    with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
        f.write("### Allocation "+str(allocation)+"\n\n| Case | Mean ms |\n|---|---:|\n")
        for name, times in values.items():
            f.write(f"| {name} | {statistics.mean(times)/1e6:.3f} |\n")

if __name__ == "__main__":
    main()
