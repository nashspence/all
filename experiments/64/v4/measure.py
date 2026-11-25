"""Trusted outer timer for the finite raw-budget / generic-profile experiment."""
import argparse
import copy
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

# In CI this file and these imports execute from the pinned authority checkout.
import central
import accept

PRODUCT_BASE = "03de186a044c9c6b365347485a6c4093ce831c79"
CORE = "public-linux-x64-4cpu-v1"
SYNC = "public-linux-x64-4cpu-sync-v1"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def git(tree, *args):
    return subprocess.check_output(["git", "-C", str(tree), *args], text=True).strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def busy(stop, ready):
    payload = bytes(range(256)) * 4096
    ready.put(True)
    while not stop.is_set():
        hashlib.sha256(payload).digest()


def profile_admission(record):
    value = central.evaluate(record)
    return {CORE: value["core_admitted"], SYNC: value["sync_admitted"]}, value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("allocation", type=int)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    require(1 <= args.allocation <= 24, "allocation must be 1..24")
    candidate = Path(os.environ.get("CANDIDATE_TREE", Path.cwd())).resolve()
    authority_dir = Path(__file__).resolve().parent
    authority_tree = authority_dir.parents[2]
    contract_path = authority_dir / "design_contract.json"
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)
    if not args.smoke:
        require(git(candidate, "rev-parse", "HEAD") == os.environ["GITHUB_SHA"], "candidate source mismatch")
        require(git(authority_tree, "rev-parse", "HEAD") == os.environ["AUTHORITY_REVISION"], "authority source mismatch")
        require(candidate != authority_tree, "authority must be independent of candidate checkout")
        require(Path(central.__file__).resolve().parent == authority_dir and Path(accept.__file__).resolve().parent == authority_dir,
                "authority module shadowing")
        require(sys.version_info[:3] == (3, 11, 9), "central runtime mismatch")
        require(git(candidate, "diff", "--name-only", PRODUCT_BASE, "HEAD", "--", "all_policy", "pyproject.toml", ".github/workflows/all.yml") == "", "frozen subject changed")
    spec = importlib.util.spec_from_file_location("_candidate_workloads", candidate / "experiments/64/v4/workloads.py")
    workloads_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = workloads_module
    spec.loader.exec_module(workloads_module)
    started = time.time_ns()
    # Actual unapproved manifest edit in the candidate checkout. The runner must
    # continue reading the separately pinned authority and its unchanged budgets.
    proposed_path = candidate / "experiments/64/v4/design_contract.json"
    proposed_before = proposed_path.read_bytes()
    proposal = copy.deepcopy(contract)
    for value in proposal["operations"].values():
        value["budget_ns"] = 10**15
        value["profile"] = CORE
    proposed_after = (json.dumps(proposal, sort_keys=True) + "\n").encode()
    # Local smoke can point both trees at the same source. It does not edit that file.
    if not args.smoke:
        proposed_path.write_bytes(proposed_after)
    # Resolve the authoritative bytes again AFTER the unapproved proposal exists.
    # A candidate-checkout contract would now select the wrong values.
    require(contract_path.read_bytes() == contract_bytes, "candidate edit reached authority")
    contract = json.loads(contract_path.read_bytes())
    record = {
        "format": "all-absolute-budget-experiment/v4", "allocation": args.allocation,
        "source": os.environ.get("GITHUB_SHA", "LOCAL_SMOKE"),
        "authority_revision": os.environ.get("AUTHORITY_REVISION", "LOCAL_SMOKE"),
        "product_base": PRODUCT_BASE, "smoke": args.smoke,
        "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "runner_name": os.environ.get("RUNNER_NAME"), "started_unix_ns": started,
        "central_source_sha256": digest(Path(central.__file__).read_bytes()),
        "accept_source_sha256": digest(Path(accept.__file__).read_bytes()),
        "timer_source_sha256": digest(Path(__file__).read_bytes()),
        "workloads_source_sha256": digest(Path(workloads_module.__file__).read_bytes()),
        "contract_sha256": digest(contract_bytes),
        "product_protocol_sha256": digest((candidate / "all_policy/protocol.py").read_bytes()),
        "authority_test": {"candidate_original_sha256": digest(proposed_before),
                           "candidate_proposal_sha256": digest(proposed_after),
                           "candidate_manifest_really_mutated": not args.smoke,
                           "authority_reloaded_after_candidate_proposal": True,
                           "proposed_budget_ns": 10**15,
                           "loaded_from_separate_pinned_tree": not args.smoke},
        "samples": {}, "decisions": {}, "execution_order": [],
    }
    try:
        with tempfile.TemporaryDirectory(prefix="all-absolute-", dir=os.environ.get("RUNNER_TEMP")) as td:
            scratch = Path(td)
            probe_context = central.prepare(scratch / "probes")
            subject = workloads_module.Workloads(scratch / "subject", candidate)
            record["fixture_sha256"] = digest(b"\0".join(subject.source_parts))
            record["preflight"] = central.collect(probe_context)
            admitted, decision = profile_admission(record["preflight"])
            record["admission"] = admitted
            record["admission_details"] = decision
            cases = [(operation, mode) for operation in contract["operations"] for mode in ("normal", "wait")]
            cases += [(operation, "extra50") for operation in contract["operations"] if operation.startswith("policy")]
            cases += [("policy16_p1", "periodic_wait"), ("policy16_p1", "override_wait"), ("cycle48", "cycle_wait")]
            for operation, mode in cases:
                record["samples"][f"{operation}/{mode}"] = []
            for repeat in range(3):
                offset = (args.allocation + repeat - 1) % len(cases)
                order = cases[offset:] + cases[:offset]
                if (args.allocation + repeat) % 2 == 0:
                    order.reverse()
                for operation, mode in order:
                    case = f"{operation}/{mode}"
                    wait_ns = contract["operations"][operation]["budget_ns"] + 16_000_000
                    start = time.perf_counter_ns()
                    result, claims, injected = subject.execute(operation, mode, repeat, wait_ns)
                    wall_ns = time.perf_counter_ns() - start
                    if operation.startswith("policy") or operation == "cycle48":
                        expected_count = 48 if operation == "cycle48" else int(operation.removeprefix("policy").split("_p")[0])
                        if mode == "extra50":
                            expected_count = expected_count * 3 // 2
                        require(result.get("count") == expected_count, "adapter changed required work extent")
                    subject.verify(result)
                    require(wall_ns > 0 and wall_ns >= injected, "invalid elapsed observation")
                    record["samples"][case].append({"wall_ns": wall_ns, "verified": True,
                                                   "injected_wait_ns": injected, "candidate_claims": claims})
                    record["execution_order"].append([repeat, case])
            # Admission is frozen before the subject. Later controls do not erase misses.
            for case, samples in record["samples"].items():
                operation = case.split("/")[0]
                claims = next((s["candidate_claims"] for s in samples if s["candidate_claims"]), None)
                record["decisions"][case] = accept.evaluate(operation, [s["wall_ns"] for s in samples], admitted, contract, claims)
            decision_bytes = json.dumps(record["decisions"], sort_keys=True)
            record["postflight"] = central.collect(probe_context)
            record["postflight_admission"] = profile_admission(record["postflight"])[0]
            # Real CPU contention; resource metadata remains unchanged. This is a
            # sensitivity witness, not an assertion that every busy worker is invalid.
            context = mp.get_context("fork")
            stop, ready = context.Event(), context.Queue()
            competitors = [context.Process(target=busy, args=(stop, ready)) for _ in range(8)]
            for process in competitors:
                process.start()
            try:
                for _ in competitors:
                    require(ready.get(timeout=10) is True, "CPU-pressure startup")
                record["cpu_pressure"] = central.collect(probe_context)
                record["cpu_pressure_admission"] = profile_admission(record["cpu_pressure"])[0]
            finally:
                stop.set()
                for process in competitors:
                    process.join(timeout=3)
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=3)
                record["pressure_workers_joined"] = all(not p.is_alive() for p in competitors)
                ready.close()
            # Actual one-CPU affinity cannot satisfy the four-CPU profile.
            original_affinity = os.sched_getaffinity(0)
            try:
                os.sched_setaffinity(0, {min(original_affinity)})
                record["one_cpu"] = central.collect(probe_context)
                record["one_cpu_admission"] = profile_admission(record["one_cpu"])[0]
            finally:
                os.sched_setaffinity(0, original_affinity)
            record["authority_test"]["postflight_cannot_rewrite_decisions"] = decision_bytes == json.dumps(record["decisions"], sort_keys=True)
            record["authority_test"]["authority_file_unchanged"] = contract_path.read_bytes() == contract_bytes
            record["authority_test"]["candidate_proposal_did_not_activate"] = all(
                v.get("budget_ns") == contract["operations"][case.split("/")[0]]["budget_ns"]
                for case, v in record["decisions"].items())
            require(all(record["authority_test"][key] for key in ("postflight_cannot_rewrite_decisions", "authority_file_unchanged", "candidate_proposal_did_not_activate")), "authority boundary failed")
            record["verified"] = True
    finally:
        if not args.smoke:
            proposed_path.write_bytes(proposed_before)
    if not args.smoke:
        require(not git(candidate, "status", "--porcelain", "--untracked-files=no"), "tracked source not restored")
    record["finished_unix_ns"] = time.time_ns()
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    Path("absolute-observation.json").write_text(line + "\n")
    print("ABSOLUTE_OBSERVATION " + line, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("## Raw wall-clock experiment\n\nProfile admission: " + json.dumps(admitted) + "\n\n| Case | Budget ms | Raw max ms | Verdict |\n|---|---:|---:|---|\n")
            for case, value in record["decisions"].items():
                f.write(f"| {case} | {value['budget_ns']/1e6:g} | {value['raw_max_ns']/1e6:.3f} | {value['verdict']} |\n")


if __name__ == "__main__":
    main()
