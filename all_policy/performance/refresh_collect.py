"""Fixed central qualification collectors; their packets never grant acceptance.

The normal runner requires live approval. This trusted main-only collector uses
its private measurement boundary to obtain evidence for reviewed enrollment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from .approval import source_digest
from .contracts import Limit, evaluate, load_authority
from .profiles import CAPS_NS, CORE, PREPARED_EXT4, admit

AUTHORITY = "ed6c2dd701d5a8969166872af48b9d434d6f8af3"
LIMITS = {"check_repository16_warm": 20_000_000,
          "check_repository16_cold": 125_000_000}
DOCUMENTS = {"limits": "828acfefbd21e7131fb3a85740890c68700e8e933b667bcf30fbf9415117f327",
             "bindings": "28cae08101d7f7c43e9d006ef7ae6ab826a0aa2d47323f3c1104dfba4c1c91d1"}
STORAGE_LIMITS = {"atomic16_p1": 320_000_000, "atomic16_p2": 320_000_000,
                  "atomic16_p4": 320_000_000, "append64_sync": 1_280_000_000,
                  "sqlite64_delete_extra": 1_280_000_000, "sqlite64_wal_full": 1_280_000_000,
                  "sqlite64_delete_extra_batch": 320_000_000, "sqlite64_wal_full_batch": 320_000_000}
CONSUMERS = {"fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
             "riverhog": "be483fd6d567616d5fcd355202d61f1e682efe75"}


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _complete_preflight(evidence):
    _require(evidence.get("errors") == [], "probe execution/correctness error")
    samples = evidence.get("samples_ns", {})
    _require(set(samples) == set(CAPS_NS), "incomplete probe inventory")
    _require(all(isinstance(v, list) and len(v) == 3 and
                 all(type(n) is int and n > 0 for n in v) for v in samples.values()),
             "incomplete probe observations")
    for phase in ("metadata", "metadata_after"):
        row = evidence.get(phase, {})
        for name in ("system", "machine", "python", "root", "cpu_model", "image_os", "image_version"):
            _require(isinstance(row.get(name), str) and row[name], "missing " + name)
        for name in ("logical_cpus", "affinity_count", "memory_total_bytes", "free_bytes", "device"):
            _require(type(row.get(name)) is int and row[name] >= 0, "missing " + name)
        _require(isinstance(row.get("topology"), dict) and "blockdevices" in row["topology"],
                 "missing topology")
        mount = row.get("mount", {})
        _require(all(isinstance(mount.get(k), str) and mount[k]
                     for k in ("source", "fstype", "options")), "incomplete mount")
        _require(not row.get("mount_error") and not row.get("topology_error"), "metadata collection failed")
        _require("cpu_max" in row and "memory_max" in row, "quota metadata missing")
        cpu = row["cpu_max"]
        _require(cpu is None or (isinstance(cpu, str) and
                 re.fullmatch(r"(?:max|[1-9][0-9]*) [1-9][0-9]*", cpu)), "malformed CPU quota")
        memory = row["memory_max"]
        _require(memory is None or memory == "max" or
                 (isinstance(memory, str) and re.fullmatch(r"[1-9][0-9]*", memory)), "malformed memory quota")
    _require(all(evidence["metadata"].get(k) == evidence["metadata_after"].get(k)
                 for k in ("root", "device", "mount")), "resource changed during preflight")


def _shared(record):
    from .runner import source_info
    expected = source_info()
    actual = record.get("shared_source", {})
    _require(all(actual.get(key) == expected[key] for key in ("files_sha256", "package_sha256")),
             "raw measurement source differs from the installed shared implementation")


def _core(packet):
    record = packet["raw"]
    _shared(record)
    _require(record.get("authority_revision") == AUTHORITY and record.get("repository") == "nashspence/all",
             "wrong fixed authority")
    _require(record.get("candidate_revision") == packet["source_commit"], "wrong measured source")
    _require(record.get("limits_sha256") == DOCUMENTS["limits"] and
             record.get("bindings_sha256") == DOCUMENTS["bindings"], "changed fixed workload/limits")
    _require(not record.get("error") and not record.get("source_error"), "collection/source failed")
    _require(set(record.get("operations", {})) == set(LIMITS), "incomplete operation inventory")
    preflights = record.get("preflights", {})
    _require(len(preflights) == 1, "one complete core preflight required")
    evidence = next(iter(preflights.values()))
    _complete_preflight(evidence)
    admission = admit(CORE, evidence)
    for name, cap in LIMITS.items():
        row = record["operations"][name]
        _require(row.get("admission") == admission, "recorded admission differs")
        observations = row.get("observations")
        _require(isinstance(observations, list), "missing observations")
        expected = evaluate(Limit(CORE, cap), admission, observations)
        _require(row.get("decision") == expected, "recorded raw verdict differs")
        _require(not row.get("excluded_stages", {}).get("error"), "operation/lifecycle error")
        if admission["admitted"]:
            if expected["verdict"] != "pass":
                return "failed"
        else:
            _require(not observations, "product executed after rejection")
    expected = "pass" if admission["admitted"] else "unqualified"
    _require(record.get("verdict") == expected, "inconsistent overall verdict")
    return "pass" if admission["admitted"] else "environment"


def _storage(packet):
    record = packet["raw"]
    _shared(record)
    _require(record.get("source_revision") == packet["source_commit"], "wrong measured source")
    _require(record.get("profile") == PREPARED_EXT4 and record.get("errors") == [], "storage controller failed")
    _require(record.get("whole_worker_complete") is True and record.get("setup_cleanup_within_60s") is True
             and type(record.get("setup_cleanup_ns")) is int and 0 < record["setup_cleanup_ns"] <= 60_000_000_000,
             "resource did not complete within unchanged allowance")
    _require(record.get("preparation", {}).get("status") == "cleaned", "owned cleanup incomplete")
    collection = record["collection"]
    _require(collection.get("errors") == [] and collection.get("postflight_intact") is True,
             "storage collection incomplete")
    for call in (record["collection_command"], collection["generic_command"]):
        _require(call.get("returncode") == 0 and not call.get("timed_out"), "storage command failed")
    _require(set(collection.get("probe_evidence", {})) ==
             {phase + "-" + root for phase in ("preflight", "postflight")
              for root in ("root_loop_a", "root_loop_b")}, "missing paired probes")
    for evidence in collection["probe_evidence"].values():
        _complete_preflight(evidence)
        _complete_preflight(evidence["prepared_pair"]["evidence"])
        _require(admit(PREPARED_EXT4, evidence)["admitted"], "prepared resource unqualified")
    generic = collection["generic"]
    _shared(generic)
    _require(generic.get("complete") is True and generic.get("errors") == []
             and set(generic["operations"]) == set(STORAGE_LIMITS), "generic inventory incomplete")
    for name, cap in STORAGE_LIMITS.items():
        row = generic["operations"][name]
        _require(row.get("limit_ns") == cap, "generic limit changed")
        verdict = evaluate(Limit(PREPARED_EXT4, cap), {"profile": PREPARED_EXT4, "admitted": True}, row["observations"])
        if verdict["verdict"] != "pass":
            return "failed"
    _require(set(collection.get("consumers", {})) == set(CONSUMERS), "consumer applicability missing")
    for kind, source in CONSUMERS.items():
        row = collection["consumers"][kind]
        result = row["result"]
        _shared({"shared_source": result.get("shared_source_info")})
        _require(row["command"].get("returncode") == 0 and not row["command"].get("timed_out")
                 and result.get("status") == "complete" and result.get("errors") == [], "consumer incomplete")
        _require(result.get("consumer_source", {}).get("revision") == source, "consumer source changed")
        _require(result.get("shared_checkout", {}).get("revision") == packet["source_commit"], "shared source changed")
        rows = result.get("observations", [])
        _require(len(rows) == 3 and all(r.get("completed") is True and r.get("verified") is True
                 and not r.get("error") and type(r.get("elapsed_ns")) is int and r["elapsed_ns"] > 0
                 for r in rows), "consumer raw evidence incomplete")
        _require(len(result.get("verification", [])) == 3 and all(r.get("verified") is True
                 and r.get("publications") == 16 for r in result["verification"]), "consumer verification incomplete")
        # #66's consumer 320ms comparison is engineering evidence, not an approved budget.
    return "pass"


def classify(packet, kind, expected_digest):
    """Recompute verdict from original packet; ambiguity never uses availability tolerance."""
    try:
        _require(packet.get("schema") == 1 and packet.get("qualification_only") is True,
                 "qualification packet required")
        _require(packet.get("source_digest") == expected_digest and not packet.get("error"),
                 "source/collection failed")
        return _core(packet) if kind == "core" else _storage(packet) if kind == "storage" else "incomplete"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "incomplete"


def collect(args):
    from . import runner
    workspace = Path(args.workspace).resolve()
    packet = {"schema": 1, "qualification_only": True, "cohort": args.cohort, "slot": args.slot,
              "run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")),
              "source_commit": os.environ.get("GITHUB_SHA"), "source_digest": source_digest(),
              "workflow_sha": os.environ.get("REFRESH_WORKFLOW_SHA"),
              "runner_name": os.environ.get("RUNNER_NAME"), "raw": None, "error": None}
    started = time.perf_counter_ns()
    try:
        _require(os.environ.get("GITHUB_REPOSITORY") == "nashspence/all" and
                 os.environ.get("GITHUB_REF") == "refs/heads/main" and
                 os.environ.get("GITHUB_ACTIONS") == "true" and packet["run_attempt"] == 1,
                 "central main first-attempt qualification only")
        _require(os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted", "public hosted worker required")
        runtime = workspace / "runtime"
        actual = subprocess.check_output(["git", "-c", "safe.directory=" + str(runtime), "-C", str(runtime),
                                          "rev-parse", "HEAD"], text=True, timeout=10).strip()
        _require(actual == packet["source_commit"], "runtime checkout differs from merged main")
        _require(source_digest(runtime / "all_policy") == packet["source_digest"], "installed bytes differ")
        _require(not Path(runner.__file__).resolve().is_relative_to(workspace), "installed runtime must be outside source")
        _require(platform.python_version() == ("3.11.9" if args.kind == "core" else "3.12.16"),
                 "fixed runtime required")
        if args.kind == "core":
            subject = workspace / "subject"
            _require(runner._candidate_revision(subject) == actual, "candidate differs from merged runtime")
            authority = load_authority(workspace / "authority", AUTHORITY, "nashspence/all")
            _require(authority.limits_sha256 == DOCUMENTS["limits"] and
                     authority.bindings_sha256 == DOCUMENTS["bindings"], "frozen authority differs")
            root = Path(os.environ["RUNNER_TEMP"]) / "core-refresh-storage"
            root.mkdir()
            with runner._ProcessScope():
                packet["raw"] = runner._run_suite(authority, subject, {CORE: root})
        else:
            packet["raw"] = json.loads((Path(args.raw) / "record.json").read_text())
        _require(source_digest() == packet["source_digest"], "installed source changed")
    except Exception as error:
        packet["error"] = type(error).__name__ + ": " + str(error)
    packet["collection_wall_ns"] = time.perf_counter_ns() - started
    packet["outcome"] = classify(packet, args.kind, packet["source_digest"])
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / f"worker-{args.cohort}-{args.slot}.json").write_text(json.dumps(packet, sort_keys=True) + "\n")
    print(json.dumps({"outcome": packet["outcome"], "qualification_only": True, "error": packet["error"]}))
    return 0 if packet["outcome"] in {"pass", "environment"} else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "check-enrollment":
        parser = argparse.ArgumentParser()
        parser.add_argument("--registry", required=True)
        parser.add_argument("--profile", required=True)
        parser.add_argument("--qualification-only", action="store_true")
        args = parser.parse_args(argv[1:])
        from .approval import require_current
        from .refresh import validate_registry
        registry = validate_registry(json.loads(Path(args.registry).read_text()))
        entry = registry["profiles"].get(args.profile)
        if args.qualification_only or entry is None or entry["source_digest"] != source_digest():
            print("Qualification evidence only: this implementation awaits reviewed enrollment.")
            return 0
        print(json.dumps(require_current({args.profile}), sort_keys=True))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("core", "storage"))
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw")
    parser.add_argument("--cohort", type=int, choices=(1, 2), default=1)
    parser.add_argument("--slot", type=int, choices=range(1, 13), required=True)
    return collect(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
