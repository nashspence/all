"""Finite raw storage experiment. Run from the separately pinned authority tree."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

import storage_cases

HERE = Path(__file__).resolve().parent
CORE = "public-linux-x64-4cpu-v1"
STORAGE_LIMITS = {operation: (100_000_000 if operation.startswith(("copy", "atomic")) else 150_000_000)
                  for operation in storage_cases.OPERATIONS}
CORE_LIMITS = {"policy16_p1": 20_000_000, "policy16_p2": 30_000_000, "policy16_p4": 30_000_000,
               "policy512_p1": 500_000_000, "policy512_p2": 350_000_000, "policy512_p4": 300_000_000,
               "cycle48": 50_000_000, "cold16": 125_000_000, "copy16": 20_000_000}
PRODUCT = "03de186a044c9c6b365347485a6c4093ce831c79"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def decide(samples, budget, admitted):
    if len(samples) != 3 or any(not s.get("verified") or type(s.get("wall_ns")) is not int or s["wall_ns"] <= 0 for s in samples):
        return "invalid_evidence"
    if not admitted:
        return "unqualified"
    misses = sum(s["wall_ns"] > budget for s in samples)
    return "pass" if not misses else "all_over" if misses == 3 else "mixed_miss"


def storage_admission(topology, core_admitted, kind):
    reasons = []
    if not core_admitted:
        reasons.append("core profile not admitted")
    filesystem = topology.get("filesystem")
    if kind == "memory":
        if filesystem != "tmpfs":
            reasons.append("actual tmpfs required")
    elif not filesystem or filesystem in ("tmpfs", "ramfs", "overlay"):
        reasons.append("observed non-memory native filesystem required")
    # This is API-timing admission, never a physical persistence qualification.
    return {"admitted": not reasons, "reasons": reasons,
            "claim": "volatile software path" if kind == "memory" else "native filesystem API timing",
            "physical_persistence_qualified": False,
            "durability_cautions": topology.get("durability_cautions", [])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("allocation", type=int)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    require(1 <= args.allocation <= 24, "allocation must be 1..24")
    candidate = Path(os.environ.get("CANDIDATE_TREE", Path.cwd())).resolve()
    authority = HERE.parents[2]
    if not args.smoke:
        require(git(candidate, "rev-parse", "HEAD") == os.environ["GITHUB_SHA"], "candidate source")
        require(git(authority, "rev-parse", "HEAD") == os.environ["AUTHORITY_REVISION"], "authority source")
        require(authority != candidate, "independent authority checkout required")
        require(sys.version_info[:3] == (3, 11, 9), "pinned probe runtime required")
        require(not git(candidate, "diff", "--name-only", PRODUCT, "HEAD", "--", "all_policy", "pyproject.toml", ".github/workflows/all.yml"), "frozen product changed")
    central = module("v5_frozen_central", HERE.parent / "v4/central.py")
    product_module = module("v5_frozen_product_adapter", HERE.parent / "v4/workloads.py")
    started = time.time_ns()
    record = {"format": "all-storage-profile-experiment/v5", "allocation": args.allocation,
              "smoke": args.smoke, "source": os.environ.get("GITHUB_SHA", "LOCAL_SMOKE"),
              "authority_revision": os.environ.get("AUTHORITY_REVISION", "LOCAL_SMOKE"),
              "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
              "runner_name": os.environ.get("RUNNER_NAME"), "runner_label": os.environ.get("EXPERIMENT_RUNNER_LABEL"),
              "product_base": PRODUCT, "python": platform.python_version(),
              "started_unix_ns": started, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "hashes": {name: digest(path) for name, path in {
                  "timer": __file__, "storage_cases": storage_cases.__file__, "central": central.__file__,
                  "product_adapter": product_module.__file__, "product": candidate / "all_policy/protocol.py",
                  "plan": HERE / "PLAN.md"}.items()},
              "storage_limits_ns": STORAGE_LIMITS, "core_limits_ns": CORE_LIMITS,
              "storage": {}, "core_samples": {op: [] for op in CORE_LIMITS}, "execution_order": [], "unavailable_paths": {},
              "collection_errors": [], "complete": False}
    handles = []
    stage = "path_setup"
    try:
        native_handle = tempfile.TemporaryDirectory(prefix="all-storage-v5-", dir=os.environ.get("RUNNER_TEMP"))
        handles.append(native_handle)
        native_root = Path(native_handle.name)
        roots = {"runner_temp": native_root}
        record["path_inventory"] = {}
        record["path_checks"] = {}
        for name, path in {"runner_temp": native_root, "workspace": candidate, "tmp": Path("/tmp"), "mnt": Path("/mnt"), "shm": Path("/dev/shm")}.items():
            record["path_checks"][name] = {"exists": path.exists(), "directory": path.is_dir(),
                "writable": os.access(path, os.W_OK),
                "free_bytes": shutil.disk_usage(path).free if path.exists() else None,
                "device_number": path.stat().st_dev if path.exists() else None}
            if path.exists():
                record["path_inventory"][name] = storage_cases.topology(path)
            else:
                record["path_inventory"][name] = {"unavailable": "path does not exist"}
        shm = Path("/dev/shm")
        record["memory_required_free_bytes"] = 64 * 1024**2
        if (record["path_checks"]["shm"]["directory"] and record["path_checks"]["shm"]["writable"]
                and record["path_checks"]["shm"]["free_bytes"] >= record["memory_required_free_bytes"]
                and record["path_inventory"]["shm"].get("filesystem") == "tmpfs"):
            h = tempfile.TemporaryDirectory(prefix="all-storage-v5-", dir=shm)
            handles.append(h)
            roots["memory"] = Path(h.name)
        else:
            record["unavailable_paths"]["memory"] = "writable tmpfs /dev/shm with 64 MiB free unavailable"
        mnt = Path("/mnt")
        if mnt.is_dir() and os.access(mnt, os.W_OK) and mnt.stat().st_dev != native_root.stat().st_dev:
            h = tempfile.TemporaryDirectory(prefix="all-storage-v5-", dir=mnt)
            handles.append(h)
            roots["distinct_mnt"] = Path(h.name)
        else:
            record["unavailable_paths"]["distinct_mnt"] = "no writable distinct mounted device at /mnt; no duplicate root-disk arm"
        contexts, topologies = {}, {}
        for name in list(roots):
            stage = "storage_prepare:" + name
            try:
                contexts[name] = storage_cases.prepare(roots[name] / "storage")
                topologies[name] = storage_cases.topology(roots[name])
            except Exception as exc:
                record["unavailable_paths"][name] = {"stage": stage, "type": type(exc).__name__, "message": str(exc)}
                record["collection_errors"].append(record["unavailable_paths"][name])
                roots.pop(name)
                contexts.pop(name, None)
        stage = "core_prepare"
        product = product_module.Workloads(native_root / "product", candidate)
        probe = central.prepare(native_root / "probes")
        record["fixture_sha256"] = hashlib.sha256(b"\0".join(product.source_parts)).hexdigest()
        stage = "preflight"
        record["preflight"] = central.collect(probe)
        record["core_admission"] = central.evaluate(record["preflight"])
        admitted = record["core_admission"]["core_admitted"]
        for name in roots:
            record["storage"][name] = {"topology": topologies[name],
                "admission": storage_admission(topologies[name], admitted, name), "samples": {}, "decisions": {}}
            for op in STORAGE_LIMITS:
                record["storage"][name]["samples"][op + "/normal"] = []
            for case in ("atomic16_p1/wait", "sqlite64_wal_full/periodic_wait"):
                record["storage"][name]["samples"][case] = []
        cases = [(name, case) for name, value in record["storage"].items() for case in value["samples"]]
        cases += [("core", op) for op in CORE_LIMITS]
        for repeat in range(3):
            offset = (args.allocation + repeat - 1) % len(cases)
            order = cases[offset:] + cases[:offset]
            if (args.allocation + repeat) % 2 == 0:
                order.reverse()
            for location, case in order:
                stage = f"operation:{repeat}:{location}:{case}"
                wall_ns = None
                injected = 0
                error = None
                receipt = None
                start = time.perf_counter_ns()
                try:
                    if location == "core":
                        result, claims, _ = product.execute(case, "normal", repeat, 0)
                        require(claims is None, "unexpected product claims")
                    else:
                        op, mode = case.split("/")
                        receipt = storage_cases.execute(contexts[location], op)
                        if mode == "wait" or mode == "periodic_wait" and repeat == 1:
                            injected = STORAGE_LIMITS[op] + 16_000_000
                            time.sleep(injected / 1e9)
                    wall_ns = time.perf_counter_ns() - start
                except Exception as exc:
                    wall_ns = time.perf_counter_ns() - start
                    error = {"stage": "execute", "type": type(exc).__name__, "message": str(exc)}
                if error is None:
                    try:
                        if location == "core":
                            product.verify(result)
                        else:
                            storage_cases.verify(contexts[location], receipt)
                    except Exception as exc:
                        error = {"stage": "verify", "type": type(exc).__name__, "message": str(exc)}
                sample = {"wall_ns": wall_ns, "verified": error is None, "error": error, "injected_wait_ns": injected}
                if receipt is not None:
                    sample["receipt"] = receipt
                if location == "core":
                    record["core_samples"][case].append(sample)
                else:
                    record["storage"][location]["samples"][case].append(sample)
                record["execution_order"].append([repeat, location, case])
        stage = "classification"
        record["core_decisions"] = {op: decide(samples, CORE_LIMITS[op], admitted) for op, samples in record["core_samples"].items()}
        for name, value in record["storage"].items():
            value["decisions"] = {case: decide(samples, STORAGE_LIMITS[case.split("/")[0]], value["admission"]["admitted"])
                                  for case, samples in value["samples"].items()}
        stage = "postflight"
        record["postflight"] = central.collect(probe)
        record["postflight_core_admission"] = central.evaluate(record["postflight"])
        record["postflight_used_for_acceptance"] = False
        for name, root in roots.items():
            stage = "topology_after:" + name
            record["storage"][name]["topology_after"] = storage_cases.topology(root)
        record["complete"] = True
    except Exception as exc:
        record["collection_errors"].append({"stage": stage, "type": type(exc).__name__, "message": str(exc)})
    finally:
        for handle in reversed(handles):
            try:
                handle.cleanup()
            except Exception as exc:
                record["collection_errors"].append({"stage": "cleanup", "type": type(exc).__name__, "message": str(exc)})
    record["finished_unix_ns"] = time.time_ns()
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    Path("storage-v5-observation.json").write_text(line + "\n")
    print("STORAGE_V5_OBSERVATION " + line, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as out:
            out.write("## Storage API timing (not physical persistence qualification)\n\n")
            for name, value in record["storage"].items():
                out.write(f"### {name}: {value['topology']['filesystem']}\n\n")
                out.write("| Case | Budget ms | Raw max ms | Verdict |\n|---|---:|---:|---|\n")
                for case, samples in value["samples"].items():
                    maximum = max((s["wall_ns"] for s in samples), default=0) / 1e6
                    out.write(f"| {case} | {STORAGE_LIMITS[case.split('/')[0]]/1e6:g} | {maximum:.3f} | {value['decisions'].get(case, 'invalid_evidence')} |\n")
    if not record["complete"] or record["collection_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
