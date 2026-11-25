"""Coordinate real consumer evidence with the unchanged shared parent clock."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

SHARED_DEFAULT = "a324c2a1c203ac2478afaac127f385f9e1e264d3"
SOURCE = Path(__file__).resolve().parents[2]
PINS = {
    "fishhat": ("f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
                "9bd952bfee4c465e1fb8cf0b8d816361ff508d3c2767078795e0a30fdfb8650d",
                "e59b241a2e3af5bd2ba4e17b7b7cda8640998c3c954d7445ac796d0849054cee"),
    "riverhog": ("be483fd6d567616d5fcd355202d61f1e682efe75",
                 "16b64145aa11bfbd6d2076a7a5adc783ed7d2e000237f9c31e9977ef48815f24",
                 "9cac47ec2007496555bcea5ed210250881015780fa8ae76c84304c29b7a9de6d"),
}
HELPER_SHA256 = "d39da81d384818c2c8a920d78e82a8ac2617378932d345fe74dd94b3ae78b2b3"
SCREEN_NS = 320_000_000


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(path, *arguments):
    return subprocess.check_output(
        ["git", "-c", "safe.directory=" + str(path), "-C", str(path), *arguments],
        text=True, stderr=subprocess.PIPE, timeout=10).strip()


def checkout(path, expected, lock_hash=None):
    require(re.fullmatch(r"[0-9a-f]{40}", expected) is not None, "full source revision required")
    actual = git(path, "rev-parse", "HEAD")
    require(actual == expected, "checkout differs from selected source revision")
    git(path, "diff", "--exit-code", "HEAD", "--")
    value = {"revision": actual, "tree": git(path, "rev-parse", "HEAD^{tree}"),
             "path": str(path), "tracked_clean": True}
    if lock_hash is not None:
        value["uv_lock_sha256"] = digest(path / "uv.lock")
        require(value["uv_lock_sha256"] == lock_hash, "consumer dependency lock changed")
    return value


def save(output, record):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".partial")
    temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=tuple(PINS), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--shared-source", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--cold", action="store_true", help="include ungated complete-process diagnostic")
    args = parser.parse_args()
    args.source, args.shared_source = args.source.resolve(), args.shared_source.resolve()
    args.work, args.output = args.work.resolve(), args.output.resolve()
    record = {"schema": "all.storage66.consumer/v1", "kind": args.kind, "status": "started",
              "observations": [], "excluded_stages": {}, "verification": [], "errors": [],
              "consumer_design_authority_approved": False, "physical_persistence_proven": False,
              "coordinator_sha256": digest(__file__)}
    start = time.perf_counter_ns()
    save(args.output, record)
    try:
        require(sys.version_info[:3] == (3, 12, 16), "Python 3.12.16 required")
        require(sys.platform == "linux" and os.getresuid() == os.getresgid() == (0, 0, 0),
                "actual administrative uid/gid required")
        sys.dont_write_bytecode = True
        from all_policy.performance.contracts import Binding
        from all_policy.performance import runner

        shared_revision = os.environ.get("FROZEN_SHARED_SHA", SHARED_DEFAULT)
        consumer_revision, lock_hash, adapter_hash = PINS[args.kind]
        record["consumer_source"] = checkout(args.source, consumer_revision, lock_hash)
        record["shared_checkout"] = checkout(args.shared_source, shared_revision)
        record["experiment_revision"] = git(SOURCE, "rev-parse", "HEAD")
        record["shared_source_info"] = runner.source_info()
        expected_shared = {p.name: digest(p) for p in
                           sorted((args.shared_source / "all_policy/performance").glob("*.py"))}
        require(expected_shared and record["shared_source_info"]["files_sha256"] == expected_shared,
                "installed shared modules differ from selected shared checkout")
        record["shared_module_path"] = str(Path(runner.__file__).resolve())
        context_bytes = args.context.read_bytes()
        context = json.loads(context_bytes)
        require(context.get("status") in {"prepared", "verified"}, "native resource is not prepared")
        roots = {key: str(Path(context[key]).resolve(strict=True))
                 for key in ("root_loop_a", "root_loop_b")}
        record["resource_context_sha256"] = hashlib.sha256(context_bytes).hexdigest()
        record["resource_roots"] = roots
        args.work.mkdir(parents=True, mode=0o700, exist_ok=True)
        require(not any(args.work.iterdir()), "fresh control work directory required")
        for root in map(Path, roots.values()):
            require(not args.work.is_relative_to(root) and not args.output.is_relative_to(root)
                    and args.work.stat().st_dev != root.stat().st_dev,
                    "control evidence must remain outside measured mounts")
        (args.work / "storage-context.json").write_bytes(context_bytes)
        relative_adapter = f"experiments/66/{args.kind}_adapter.py"
        binding = Binding(
            mode="request", unit="16 serial actual consumer storage publications",
            completion="all required file/directory syncs and recurring locks complete",
            adapter=relative_adapter,
            approved_files=((relative_adapter, adapter_hash),
                            ("experiments/66/consumer_cases.py", HELPER_SHA256)))
        runner._check_files(SOURCE, binding)
        record["approved_files"] = dict(binding.approved_files)
        save(args.output, record)
        deadline = time.monotonic() + 120
        with runner._ProcessScope():
            observations, stages = runner._measure(binding, SOURCE, args.work, deadline)
            record["observations"], record["excluded_stages"] = observations, stages
            if args.cold:
                command = ("{python}", "-I", "-B", str(SOURCE / "experiments/66/consumer_cases.py"),
                           "--kind", args.kind, "--authority-root", roots["root_loop_a"],
                           "--journal-root", roots["root_loop_b"], "--cold")
                record["cold_diagnostic"] = {"scope": "fresh process, fixture initialization, 16 publications, verification, close",
                                              "latency_gate": None, "completed": False}
                try:
                    elapsed = runner._command(command, SOURCE, args.work, deadline)
                    record["cold_diagnostic"].update(elapsed_ns=elapsed, completed=True)
                except Exception as error:
                    record["cold_diagnostic"]["error"] = type(error).__name__ + ": " + str(error)
                    record["errors"].append("optional cold diagnostic incomplete")
        for name, target in (("consumer-provenance.json", "consumer_provenance"),
                             ("consumer-error.json", "worker_error")):
            path = args.work / name
            if path.exists():
                record[target] = json.loads(path.read_text())
        for repeat in range(3):
            path = args.work / f"verification-{repeat}.json"
            record["verification"].append(json.loads(path.read_text()) if path.exists() else None)
        require(checkout(args.source, consumer_revision, lock_hash) == record["consumer_source"],
                "consumer source changed during measurements")
        require(checkout(args.shared_source, shared_revision) == record["shared_checkout"],
                "shared checkout changed during measurements")
        require(runner.source_info() == record["shared_source_info"], "installed shared source changed")
        runner._check_files(SOURCE, binding)
        valid = len(record["observations"]) == 3 and not stages.get("error") and all(
            row.get("completed") is True and row.get("verified") is True and not row.get("error")
            and type(row.get("elapsed_ns")) is int and row["elapsed_ns"] > 0
            for row in record["observations"])
        valid = valid and "consumer_provenance" in record and "worker_error" not in record and all(
            isinstance(row, dict) and row.get("verified") is True and row.get("publications") == 16
            for row in record["verification"])
        if not valid:
            record["errors"].append("three complete correct raw observations and retained verification required")
        raw = [row["elapsed_ns"] for row in record["observations"]
               if type(row.get("elapsed_ns")) is int]
        over = sum(value > SCREEN_NS for value in raw)
        verdict = ("incomplete" if not valid else "pass" if over == 0 else
                   "all_over" if over == 3 else "mixed_miss")
        record["usefulness_screen"] = {"budget_ns": SCREEN_NS, "approved_consumer_budget": False,
                                        "resource_qualification_input": False, "verdict": verdict,
                                        "raw_ns": raw, "over_budget_observations": over}
        record["status"] = "complete" if valid and not record["errors"] else "failed"
    except Exception as error:
        record["status"] = "failed"
        record["errors"].append(type(error).__name__ + ": " + str(error))
        record["traceback"] = traceback.format_exc()
    record["coordinator_total_ns"] = time.perf_counter_ns() - start
    save(args.output, record)
    print(json.dumps({"kind": args.kind, "status": record["status"], "output": str(args.output),
                      "errors": record["errors"]}, sort_keys=True))
    return 0 if record["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
