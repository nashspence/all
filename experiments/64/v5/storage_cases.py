"""Native storage witnesses; no timers, budgets, admission or normalization.

The caller times execute in full and calls prepare/verify outside that timer.
Atomic cases replace 16 already-existing, synchronized 4-KiB files. Their
thread-pool construction and shutdown are timed. Batch SQLite cases acknowledge
only the entire 64-row transaction; they do not promise 64 separate commits.
copy16_sync and sqlite64_delete_full preserve v4 operations as diagnostics,
including their absence of a parent-directory synchronization for new names.
Successful sync calls establish API execution, not physical power-loss survival.
"""
import concurrent.futures as cf
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

PATTERN = bytes(range(256)) * 16
OLD = bytes(reversed(range(256))) * 16
OPERATIONS = (
    "copy16_sync", "atomic16_p1", "atomic16_p2", "atomic16_p4",
    "append64_sync", "sqlite64_delete_full", "sqlite64_delete_extra",
    "sqlite64_wal_full", "sqlite64_delete_extra_batch", "sqlite64_wal_full_batch",
)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _reset_atomic(path):
    for i in range(16):
        with (path / f"item-{i:02d}.bin").open("wb") as out:
            out.write(OLD)
            out.flush()
            os.fsync(out.fileno())
    _sync_dir(path)


def prepare(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    inputs = root / "inputs"
    inputs.mkdir()
    for i in range(16):
        (inputs / f"input-{i:02d}.bin").write_bytes(PATTERN)
    atomic = {}
    for workers in (1, 2, 4):
        path = root / f"atomic-p{workers}"
        path.mkdir()
        _reset_atomic(path)
        atomic[workers] = path
    _sync_dir(root)
    _sync_dir(root.parent)
    return {"root": root, "inputs": [inputs / f"input-{i:02d}.bin" for i in range(16)],
            "atomic": atomic, "sequence": 0}


def _replace_one(task):
    directory, i = task
    path = directory / f"item-{i:02d}.bin"
    temporary = directory / f"item-{i:02d}.tmp"
    with temporary.open("xb") as out:
        out.write(PATTERN)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, path)
    _sync_dir(directory)
    return i


def execute(context, operation):
    require(operation in OPERATIONS, "unknown storage operation")
    context["sequence"] += 1
    root = context["root"]
    sequence = context["sequence"]
    receipt = {"operation": operation, "sqlite_version": sqlite3.sqlite_version}
    if operation == "copy16_sync":
        path = root / f"copy-{sequence}"
        path.mkdir()
        for source in context["inputs"]:
            with source.open("rb") as inp, (path / source.name).open("wb") as out:
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fdatasync(out.fileno())
        _sync_dir(path)
        receipt.update(kind="copy", path=str(path), legacy_diagnostic=True)
    elif operation.startswith("atomic16_p"):
        workers = int(operation.rsplit("p", 1)[1])
        path = context["atomic"][workers]
        tasks = [(path, i) for i in range(16)]
        if workers == 1:
            values = list(map(_replace_one, tasks))
        else:
            with cf.ThreadPoolExecutor(max_workers=workers) as pool:
                values = list(pool.map(_replace_one, tasks))
        receipt.update(kind="atomic", path=str(path), workers=workers, completed=values)
    elif operation == "append64_sync":
        path = root / f"append-{sequence}"
        path.mkdir()
        _sync_dir(root)
        with (path / "log.bin").open("xb") as out:
            # Persist the new name before any per-record acknowledgment.
            _sync_dir(path)
            for _ in range(64):
                out.write(PATTERN)
                out.flush()
                os.fdatasync(out.fileno())
        _sync_dir(path)
        receipt.update(kind="append", path=str(path), acknowledgments=64)
    else:
        legacy = operation == "sqlite64_delete_full"
        batch = operation.endswith("_batch")
        wal = "_wal_" in operation
        mode = "WAL" if wal else "DELETE"
        synchronous = "EXTRA" if "_extra" in operation else "FULL"
        directory = root if legacy else root / f"sqlite-{sequence}"
        if not legacy:
            directory.mkdir()
            _sync_dir(root)
        path = directory / f"database-{sequence}.sqlite"
        db = sqlite3.connect(path)
        checkpoint = None
        try:
            require(db.execute(f"PRAGMA journal_mode={mode}").fetchone()[0] == mode.lower(), "journal mode")
            db.execute(f"PRAGMA synchronous={synchronous}")
            require(db.execute("PRAGMA synchronous").fetchone()[0] == (3 if synchronous == "EXTRA" else 2), "synchronous mode")
            db.execute("CREATE TABLE t(i INTEGER PRIMARY KEY,v BLOB)")
            db.commit()
            if not legacy:
                _sync_dir(directory)
            if batch:
                db.execute("BEGIN")
            for i in range(64):
                db.execute("INSERT INTO t VALUES(?,?)", (i, PATTERN))
                if not batch:
                    db.commit()
            if batch:
                db.commit()
            if wal:
                checkpoint = list(db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
                require(checkpoint == [0, 0, 0], "WAL checkpoint incomplete")
        finally:
            db.close()
        if not legacy:
            _sync_dir(directory)
        receipt.update(kind="sqlite", path=str(path), directory=str(directory),
                       journal_mode=mode, synchronous=synchronous, checkpoint=checkpoint,
                       batch=batch, acknowledgments=1 if batch else 64,
                       concurrent_connections=1, legacy_diagnostic=legacy)
    return receipt


def verify(context, receipt):
    path = Path(receipt["path"])
    require(path.is_relative_to(context["root"]), "receipt path outside fixture")
    kind = receipt["kind"]
    if kind == "copy":
        require(sorted(p.name for p in path.iterdir()) == [f"input-{i:02d}.bin" for i in range(16)], "copy extent")
        require(all(p.read_bytes() == PATTERN for p in path.iterdir()), "copy contents")
        shutil.rmtree(path)
    elif kind == "atomic":
        require(receipt["completed"] == list(range(16)), "replacement completion")
        require(sorted(p.name for p in path.iterdir()) == [f"item-{i:02d}.bin" for i in range(16)], "replacement extent")
        require(all(p.read_bytes() == PATTERN for p in path.iterdir()), "replacement contents")
        _reset_atomic(path)
    elif kind == "append":
        require(sorted(p.name for p in path.iterdir()) == ["log.bin"], "append extent")
        require((path / "log.bin").read_bytes() == PATTERN * 64, "append contents")
        shutil.rmtree(path)
    elif kind == "sqlite":
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            require(db.execute("SELECT i,v FROM t ORDER BY i").fetchall() == [(i, PATTERN) for i in range(64)], "database contents")
            require(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "database integrity")
        finally:
            db.close()
        if receipt["legacy_diagnostic"]:
            path.unlink()
        else:
            shutil.rmtree(receipt["directory"])
    else:
        raise ValueError(kind)


def _read(path, limit=65536):
    try:
        with open(path, "r") as inp:
            text = inp.read(limit + 1)
        return {"text": text[:limit], "truncated": len(text) > limit}
    except OSError as error:
        return {"error": f"{type(error).__name__}: {error}"}


def _command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
        output = result.stdout[:131072]
        value = {"args": args, "returncode": result.returncode,
                 "stderr": result.stderr[:4096], "truncated": len(result.stdout) > 131072}
        try:
            value["data"] = json.loads(output)
        except ValueError:
            value["output"] = output
        return value
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"args": args, "error": f"{type(error).__name__}: {error}"}


def topology(path):
    """Bounded read-only evidence. No speed or durability admission is inferred."""
    path = Path(path).resolve()
    st = path.stat()
    mount = _command(["findmnt", "--json", "--target", str(path), "--output",
                      "TARGET,SOURCE,FSTYPE,OPTIONS,FSROOT,MAJ:MIN"])
    entries = mount.get("data", {}).get("filesystems", [])
    entry = entries[0] if entries else {}
    options = entry.get("options", "").split(",")
    blocks = _command(["lsblk", "--json", "--output",
                       "NAME,KNAME,MAJ:MIN,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL,TRAN,ROTA"])
    device = f"{os.major(st.st_dev)}:{os.minor(st.st_dev)}"
    resolved = Path("/sys/dev/block") / device
    queues = {}
    loop = None
    if resolved.exists():
        resolved = resolved.resolve()
        candidates = [resolved, resolved.parent]
        for candidate in candidates:
            if (candidate / "queue").exists():
                queues[str(candidate)] = {name: _read(candidate / "queue" / name, 2048)
                                         for name in ("write_cache", "fua", "rotational", "logical_block_size", "physical_block_size")}
        backing = resolved / "loop/backing_file"
        if backing.exists():
            loop = _read(backing, 8192)
            if "text" in loop:
                backing_path = "/" + loop["text"].strip().lstrip("/")
                loop["backing_mount"] = _command(["findmnt", "--json", "--target", backing_path,
                                                  "--output", "TARGET,SOURCE,FSTYPE,OPTIONS,MAJ:MIN"])
    info = _read("/proc/self/mountinfo", 131072)
    if "text" in info:
        info["matching_lines"] = [line for line in info.pop("text").splitlines()
                                  if len(line.split()) > 2 and line.split()[2] == device]
    cautions = [option for option in options if option in
                ("nobarrier", "barrier=0", "data=writeback", "journal_async_commit")]
    if entry.get("fstype") in ("tmpfs", "ramfs"):
        cautions.append("volatile_filesystem")
    return {"path": str(path), "device": device, "filesystem": entry.get("fstype"),
            "mount_options": options, "mount": mount, "block_devices": blocks,
            "sysfs_block_path": str(resolved), "queue_metadata": queues,
            "loop_backing": loop, "mountinfo": info, "kernel_cmdline": _read("/proc/cmdline"),
            "ext4_options": _read(Path("/proc/fs/ext4") / resolved.name / "options"),
            "durability_cautions": cautions, "sqlite_version": sqlite3.sqlite_version,
            "physical_power_loss_survival_proven": False}
