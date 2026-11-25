"""Real, pinned consumer storage operations for the shared #66 experiment.

The caller owns elapsed clocks. This module emits completion and verification
only, never durations, limits, admission, or a physical-persistence assertion.
Fixtures and imports precede warm requests; no required sync is deferred into
verification or close. Product security/ownership checks are never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any
import uuid

PINS = {
    "fishhat": {
        "source": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
        "module": "fishhat_owner.checkpoint_store",
        "module_sha256": "1d81a2d001b409e27934da94b06d0cf1c37167cf4d703c547ced619097c95acb",
        "distribution": "fishhat-owner-support", "version": "0.1.0.dev0",
    },
    "riverhog": {
        "source": "be483fd6d567616d5fcd355202d61f1e682efe75",
        "module": "riverhog_client._prepared_primary_posix",
        "module_sha256": "252f7f74ac48affbe73e4bda09baf96a16d7bb59706ed2891e597e1f4bf48cb8",
        "distribution": "riverhog-client", "version": "0.1.0",
    },
}
PAYLOAD = bytes(range(256)) * 16
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def protected_root(value: str | Path) -> Path:
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "absolute protected root required")
    for part in (*reversed(path.parents), path):
        row = part.lstat()
        require(stat.S_ISDIR(row.st_mode) and row.st_uid == row.st_gid == 0
                and not row.st_mode & 0o7022, "root-owned protected ancestry required")
    require(stat.S_IMODE(path.stat().st_mode) == 0o700, "private root required")
    return path


def prepare(kind: str, authority_root: str | Path, journal_root: str | Path,
            fixture_id: str | None = None) -> dict[str, Any]:
    """Create only new owned fixtures on the caller's already-qualified mounts."""
    require(kind in PINS, "unknown consumer")
    require(sys.version_info[:3] == (3, 12, 16), "Python 3.12.16 required")
    require(sys.platform == "linux" and os.getresuid() == os.getresgid() == (0, 0, 0),
            "actual administrative uid/gid required")
    sys.dont_write_bytecode = True
    authority, journal = protected_root(authority_root), protected_root(journal_root)
    require(authority.stat().st_dev != journal.stat().st_dev, "separate capture filesystems required")
    identity = str(uuid.uuid4()) if fixture_id is None else fixture_id
    require(str(uuid.UUID(identity)) == identity, "canonical fixture UUID required")
    module = importlib.import_module(PINS[kind]["module"])
    module_path = Path(module.__file__).resolve()
    module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
    require(module_hash == PINS[kind]["module_sha256"], "pinned product module changed")
    require(importlib.metadata.version(PINS[kind]["distribution"]) == PINS[kind]["version"],
            "unexpected installed product version")
    context: dict[str, Any] = {
        "kind": kind, "id": identity, "module": module, "next_repeat": 0,
        "awaiting_verification": False, "closed": False,
        "provenance": {**PINS[kind], "module_path": str(module_path),
                       "python": sys.version, "python_executable": sys.executable,
                       "installed_distributions": sorted(
                           (d.metadata["Name"], d.version) for d in importlib.metadata.distributions())},
    }
    leaf = authority / (kind + "-" + identity)
    if kind == "fishhat":
        leaf.mkdir(mode=0o700)
        peer = journal / (kind + "-" + identity)
        peer.mkdir(mode=0o700)
        owner = {"tool": "host-ops", "id": str(uuid.uuid5(uuid.UUID(identity), "owner")),
                 "epoch": str(uuid.uuid5(uuid.UUID(identity), "epoch"))}
        journal_id = str(uuid.uuid5(uuid.UUID(identity), "journal"))
        arguments = {"owner": owner, "journal_id": journal_id}
        module.CheckpointStore.initialize(leaf, peer, **arguments)
        context.update(path=leaf, journal=peer, arguments=arguments, current=None,
                       heads=[hashlib.sha256((identity + ":" + str(i)).encode()).hexdigest()
                              for i in range(48)])
        context["store"] = module.CheckpointStore.open(leaf, peer, **arguments)
    else:
        context.update(path=leaf, expected={})
        context["store"] = module.PrimaryFiles(leaf, initialize=True)
    return context


def run(context: dict[str, Any], repeat: int) -> dict[str, Any]:
    """Complete sixteen fresh locked CAS or durable POSIX byte publications."""
    require(not context["closed"] and not context["awaiting_verification"], "invalid request state")
    require(type(repeat) is int and 0 <= repeat < 3 and repeat == context["next_repeat"],
            "exactly three ordered fresh observations required")
    store = context["store"]
    if context["kind"] == "fishhat":
        records, previous = [], context["current"]
        for index in range(16):
            current = context["heads"][repeat * 16 + index]
            with store.locked():
                records.append(store.compare_and_swap(previous, current))
            previous = current
        result = {"records": records}
    else:
        files = []
        for index in range(16):
            name = f"member-{repeat}-{index}"
            value = store.put_bytes(name, (PAYLOAD,), byte_limit=len(PAYLOAD),
                                    expected=(len(PAYLOAD), PAYLOAD_SHA256))
            files.append({"name": value.name, "bytes": value.bytes, "sha256": value.sha256})
        result = {"files": files}
    context.update(last_result=result, last_repeat=repeat, awaiting_verification=True)
    return result


def verify(context: dict[str, Any], result: dict[str, Any], repeat: int) -> dict[str, Any]:
    """Reopen real product state and independently check exact bytes/head.

    PrimaryFiles.close only releases its already-quiescent retained owner. It
    performs no write, sync, or deferred work. Reopening avoids bypassing the
    real live-owner flock. Fishhat's completed lock is already released.
    """
    require(context["awaiting_verification"] and repeat == context["last_repeat"]
            and result == context["last_result"], "no matching completed observation")
    context["store"].close()
    module, path = context["module"], context["path"]
    if context["kind"] == "fishhat":
        context["store"] = module.CheckpointStore.open(path, context["journal"],
                                                       **context["arguments"])
        observed = context["store"].read()
        independent = json.loads((path / module.CURRENT).read_bytes())
        require(set(result) == {"records"} and len(result["records"]) == 16,
                "complete checkpoint extent differs")
        previous = context["current"]
        for index, row in enumerate(result["records"]):
            current = context["heads"][repeat * 16 + index]
            require(row["previous"] == previous and row["current"] == current
                    and row["owner"] == context["arguments"]["owner"]
                    and row["journal_id"] == context["arguments"]["journal_id"],
                    "fresh CAS result differs")
            previous = current
        require(observed == independent == result["records"][-1], "reopened checkpoint bytes differ")
        require(set(p.name for p in path.iterdir()) == {module.ANCHOR, module.CURRENT},
                "unexpected checkpoint residue")
        context["current"] = previous
        checks = {"verified": True, "fresh_head": previous, "publications": 16}
    else:
        context["store"] = module.PrimaryFiles(path, initialize=False)
        expected_rows = [{"name": f"member-{repeat}-{index}", "bytes": len(PAYLOAD),
                          "sha256": PAYLOAD_SHA256} for index in range(16)]
        require(result == {"files": expected_rows}, "complete publication extent differs")
        for row in result["files"]:
            context["expected"][row["name"]] = row
        for name, row in context["expected"].items():
            with context["store"].verified(module.PrimaryByteFile(**row)) as reader:
                require(reader.read() == PAYLOAD, "reopened product bytes differ")
            require((path / name).read_bytes() == PAYLOAD, "independent file bytes differ")
        require(set(p.name for p in path.iterdir()) == {".owner", *context["expected"]},
                "unexpected primary publication residue")
        checks = {"verified": True, "publications": 16,
                  "retained_files_verified": len(context["expected"]), "bytes_per_file": len(PAYLOAD)}
    context.update(awaiting_verification=False, next_repeat=repeat + 1)
    return checks


def close(context: dict[str, Any]) -> None:
    if not context["closed"]:
        context["store"].close()
        context["closed"] = True


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=tuple(PINS), required=True)
    parser.add_argument("--authority-root", required=True)
    parser.add_argument("--journal-root", required=True)
    parser.add_argument("--fixture-id")
    parser.add_argument("--cold", action="store_true",
                        help="one complete fresh-process initialization/publication/verification/close")
    args = parser.parse_args()
    context = None
    try:
        context = prepare(args.kind, args.authority_root, args.journal_root, args.fixture_id)
        if args.cold:
            result = run(context, 0)
            checks = verify(context, result, 0)
            close(context)
            emit({"event": "closed", "result": result, "checks": checks,
                  "fixture_id": context["id"], "provenance": context["provenance"]})
            return 0
        emit({"event": "ready", "fixture_id": context["id"], "kind": args.kind,
              "path": str(context["path"]), "provenance": context["provenance"]})
        for line in sys.stdin:
            request = json.loads(line)
            command = request["command"]
            if command == "run":
                result = run(context, request["repeat"])
                emit({"event": "complete", "repeat": request["repeat"], "result": result})
            elif command == "verify":
                checks = verify(context, context["last_result"], request["repeat"])
                emit({"event": "verified", "repeat": request["repeat"], "checks": checks})
            elif command == "close":
                require(not context["awaiting_verification"], "completed observation lacks verification")
                close(context)
                emit({"event": "closed"})
                return 0
            else:
                raise ValueError("unknown command")
        raise RuntimeError("controller closed without explicit completion")
    except Exception as error:
        emit({"event": "failed", "type": type(error).__name__, "error": str(error)})
        return 1
    finally:
        if context is not None:
            close(context)


if __name__ == "__main__":
    raise SystemExit(main())
