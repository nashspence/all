"""Experimental calls to real policy APIs and simple filesystem/SQLite witnesses.

No timer, budget, calibration, reference implementation, or acceptance authority.
The independent outer harness owns elapsed-time measurement and acceptance.
"""
import concurrent.futures as cf
import importlib.util
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

SUBJECT = None
PATTERN = bytes(range(256)) * 16
WORKFLOW = ".github/workflows/all.yml"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def check_one(task):
    index, path = task
    return index, SUBJECT.check_repository(path, "nashspence/all")


class Workloads:
    def __init__(self, root, product_tree):
        global SUBJECT
        self.root = Path(root)
        self.product_tree = Path(product_tree)
        self.root.mkdir(parents=True)
        spec = importlib.util.spec_from_file_location("_policy_subject", self.product_tree / "all_policy/protocol.py")
        SUBJECT = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = SUBJECT
        spec.loader.exec_module(SUBJECT)
        template = (self.product_tree / WORKFLOW).read_text()
        self.subjects, self.inputs = [], []
        self.source_parts = []
        for i in range(16):
            path = self.root / f"subject-{i:02d}" / WORKFLOW
            path.parent.mkdir(parents=True)
            content = template.replace("name: all\n", f"name: all calibration {i}\n", 1).replace("17 3 * * *", f"{i} 3 * * *", 1)
            path.write_text(content)
            self.source_parts.append(content.encode())
            self.subjects.append(path.parent.parent.parent)
            input_path = self.root / f"input-{i:02d}.bin"
            input_path.write_bytes(PATTERN)
            self.inputs.append(input_path)
            require(SUBJECT.check_repository(self.subjects[-1], "nashspence/all") == (), "valid fixture rejected")
        invalid = self.root / "invalid" / WORKFLOW
        invalid.parent.mkdir(parents=True)
        invalid.write_text("name: invalid\non: push\n")
        require(bool(SUBJECT.check_repository(invalid.parent.parent.parent, "nashspence/all")), "negative fixture accepted")
        self.sequence = 0

    def policy(self, count, workers):
        tasks = [(i % 16, str(self.subjects[i % 16])) for i in range(count)]
        if workers == 1:
            return list(map(check_one, tasks))
        with cf.ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork")) as pool:
            return list(pool.map(check_one, tasks, chunksize=1))

    def execute(self, operation, mode, repeat, wait_ns):
        """All operation work is here; the caller times this complete call."""
        self.sequence += 1
        extra = mode == "extra50"
        if operation.startswith("policy"):
            extent, workers = operation.removeprefix("policy").split("_p")
            count = int(extent) * (3 if extra else 2) // 2
            result = {"kind": "policy", "count": count, "values": self.policy(count, int(workers))}
        elif operation == "cycle48":
            values = []
            for position in range(3):
                values += self.policy(16, 1)
                if mode == "cycle_wait" and position == 1:
                    time.sleep(0.064)
            result = {"kind": "policy", "count": 48, "values": values}
        elif operation == "cold16":
            code = (
                "import importlib.util,sys; "
                "s=importlib.util.spec_from_file_location('p',sys.argv[1]); "
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); "
                "r=[m.check_repository(p,'nashspence/all') for p in sys.argv[2:]]; "
                "assert r==[()]*16;print('verified:16')"
            )
            value = subprocess.check_output([sys.executable, "-c", code, str(self.product_tree / "all_policy/protocol.py"), *map(str, self.subjects)], text=True)
            result = {"kind": "cold", "value": value.strip()}
        elif operation in ("copy16", "copy16_sync"):
            destination = self.root / f"output-{self.sequence}"
            destination.mkdir()
            for source in self.inputs:
                path = destination / source.name
                with source.open("rb") as inp, path.open("wb") as out:
                    shutil.copyfileobj(inp, out)
                    if operation == "copy16_sync":
                        out.flush()
                        os.fdatasync(out.fileno())
            if operation == "copy16_sync":
                fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            result = {"kind": "copy", "path": destination}
        elif operation == "sqlite64":
            path = self.root / f"database-{self.sequence}.sqlite"
            db = sqlite3.connect(path)
            try:
                require(db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete", "journal mode")
                db.execute("PRAGMA synchronous=FULL")
                require(db.execute("PRAGMA synchronous").fetchone()[0] == 2, "sync mode")
                db.execute("CREATE TABLE t(i INTEGER PRIMARY KEY,v BLOB)")
                db.commit()
                for i in range(64):
                    db.execute("INSERT INTO t VALUES(?,?)", (i, PATTERN))
                    db.commit()
            finally:
                db.close()
            result = {"kind": "sqlite", "path": path}
        else:
            raise ValueError(operation)
        injected = 0
        if mode in ("wait", "override_wait") or mode == "periodic_wait" and repeat == 1:
            time.sleep(wait_ns / 1e9)
            injected = wait_ns
        if mode == "cycle_wait":
            injected = 64_000_000
        # Deliberately untrusted claims exercise the outer harness's authority.
        claims = {"elapsed_ns": 1, "budget_ns": 10**15, "profile": "unlimited"} if mode == "override_wait" else None
        return result, claims, injected

    def verify(self, result):
        kind = result["kind"]
        if kind == "policy":
            require(result["values"] == [(i % 16, ()) for i in range(result["count"])], "policy outputs")
        elif kind == "cold":
            require(result["value"] == "verified:16", "cold outputs")
        elif kind == "copy":
            path = result["path"]
            require(sorted(p.name for p in path.iterdir()) == sorted(p.name for p in self.inputs), "copy extent")
            require(all((path / p.name).read_bytes() == PATTERN for p in self.inputs), "copy contents")
            shutil.rmtree(path)
        elif kind == "sqlite":
            path = result["path"]
            with sqlite3.connect(path) as db:
                require(db.execute("SELECT i,v FROM t ORDER BY i").fetchall() == [(i, PATTERN) for i in range(64)], "database output")
                require(db.execute("PRAGMA integrity_check").fetchone() == ("ok",), "database integrity")
            path.unlink()
        else:
            raise ValueError(kind)
