"""Recompute the frozen raw-budget experiment; no fitting or time adjustment."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import statistics

import accept
import central

HERE = Path(__file__).resolve().parent
CORE = "public-linux-x64-4cpu-v1"
SYNC = "public-linux-x64-4cpu-sync-v1"
PHASES = ("preflight", "postflight", "cpu_pressure", "one_cpu")
PRODUCT = "03de186a044c9c6b365347485a6c4093ce831c79"
CANDIDATE_REVISION = "ce6c39ce904c13aa8e6d5a6c619b6d2f35d47a58"
AUTHORITY_REVISION = "3c88f1b3bf28b4fe5ae8973ff40412be1c049952"
FIXTURE = "e2b3a325c2656969cc88573c78f625d0ae1d08578227fef4c6092de71123bf5a"
PROTOCOL = "967e0c485c3ea2f50c82cc16f3971ca1c276182eda929299cf53e37b20cffc8a"
VERDICTS = ("pass", "mixed_miss", "all_over", "unqualified", "invalid_evidence")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def summary(values):
    return None if not values else {"minimum": min(values), "median": statistics.median(values),
                                   "mean": statistics.mean(values), "maximum": max(values)}


def admission(probes):
    detail = central.evaluate(probes)
    return {CORE: detail["core_admitted"], SYNC: detail["sync_admitted"]}, detail


def expected_wait(case, repeat, contract):
    operation, mode = case.split("/")
    if mode in ("wait", "override_wait"):
        return contract["operations"][operation]["budget_ns"] + 16_000_000
    if mode == "periodic_wait" and repeat == 1:
        return 36_000_000
    return 64_000_000 if mode == "cycle_wait" else 0


def analyze(collection):
    contract_bytes = (HERE / "design_contract.json").read_bytes()
    contract = json.loads(contract_bytes)
    operations = contract["operations"]
    cases = [f"{op}/{mode}" for op in operations for mode in ("normal", "wait")]
    cases += [f"{op}/extra50" for op in operations if op.startswith("policy")]
    cases += ["policy16_p1/periodic_wait", "policy16_p1/override_wait", "cycle48/cycle_wait"]
    require(len(cases) == 31 and len(operations) == 11, "changed operation inventory")
    require(collection.get("complete") is True and collection.get("run_attempt") == 1, "incomplete or rerun collection")
    for key in ("source", "authority_revision"):
        require(re.fullmatch("[0-9a-f]{40}", collection.get(key, "")), "missing exact " + key)
    require(collection["source"] != collection["authority_revision"], "candidate and authority revision must differ")
    require(collection["source"] == CANDIDATE_REVISION and collection["authority_revision"] == AUTHORITY_REVISION, "different predeclared campaign")
    records = sorted(collection["records"], key=lambda r: r["allocation"])
    require([r["allocation"] for r in records] == list(range(1, 25)), "need exactly allocations 1-24")
    for key in ("job_id", "runner_id"):
        values = [r.get(key) for r in records]
        require(all(type(v) is int and v > 0 for v in values) and len(set(values)) == 24, "missing or duplicate " + key)
    source_hashes = {key: sha((HERE / name).read_bytes()) for key, name in (
        ("central_source_sha256", "central.py"), ("accept_source_sha256", "accept.py"),
        ("timer_source_sha256", "measure.py"), ("workloads_source_sha256", "workloads.py"))}
    proposal = json.loads(contract_bytes)
    for value in proposal["operations"].values():
        value.update(budget_ns=10**15, profile=CORE)
    proposal_hash = sha((json.dumps(proposal, sort_keys=True) + "\n").encode())
    recomputed, phase_results = {}, {}
    for record in records:
        allocation = record["allocation"]
        prefix = f"allocation {allocation}: "
        require(record.get("format") == "all-absolute-budget-experiment/v4", prefix + "format")
        require(record.get("verified") is True and record.get("smoke") is False, prefix + "unverified or smoke")
        for key in ("source", "authority_revision"):
            require(record.get(key) == collection[key], prefix + key)
        require(str(record.get("run_id")) == str(collection["run_id"]) and str(record.get("run_attempt")) == "1", prefix + "run identity")
        require(record.get("product_base") == PRODUCT and record.get("fixture_sha256") == FIXTURE and record.get("product_protocol_sha256") == PROTOCOL, prefix + "product/fixture identity")
        require(record.get("contract_sha256") == sha(contract_bytes), prefix + "contract hash")
        require(all(record.get(key) == value for key, value in source_hashes.items()), prefix + "source hash")
        authority = record["authority_test"]
        flags = ("candidate_manifest_really_mutated", "loaded_from_separate_pinned_tree", "authority_reloaded_after_candidate_proposal", "postflight_cannot_rewrite_decisions", "authority_file_unchanged", "candidate_proposal_did_not_activate")
        require(all(authority.get(key) is True for key in flags), prefix + "authority boundary")
        require(authority.get("candidate_original_sha256") == sha(contract_bytes) and authority.get("candidate_proposal_sha256") == proposal_hash and proposal_hash != sha(contract_bytes), prefix + "manifest mutation evidence")
        require(authority.get("proposed_budget_ns") == 10**15, prefix + "proposal dose")
        require(record.get("pressure_workers_joined") is True, prefix + "unjoined competitors")
        phase_results[allocation] = {}
        for phase in PHASES:
            probe = record[phase]
            require(set(probe["samples_ns"]) == set(central.CAPS_NS), prefix + phase + " probes")
            require(set(probe["errors"]) == set(central.CAPS_NS), prefix + phase + " error inventory")
            require(probe.get("verified") is (not any(probe["errors"].values())), prefix + phase + " verification flag")
            for name, values in probe["samples_ns"].items():
                require(len(values) == 3 and all(type(v) is int and v > 0 for v in values), prefix + phase + "/" + name + " samples")
            expected_order = {(i, name) for i in range(3) for name in central.CAPS_NS}
            require(len(probe["order"]) == 15 and set(map(tuple, probe["order"])) == expected_order, prefix + phase + " order")
            for when in ("metadata", "metadata_after"):
                metadata = probe[when]
                require(metadata["python"] == "3.11.9" and metadata["source_sha256"] == source_hashes["central_source_sha256"], prefix + phase + " probe runtime/source")
            maps, detail = admission(probe)
            field = "admission" if phase == "preflight" else phase + "_admission"
            require(maps == record[field], prefix + phase + " admission mismatch")
            if phase == "preflight":
                require(detail == record["admission_details"], prefix + "admission reasons mismatch")
            phase_results[allocation][phase] = {"admission": maps, "details": detail}
        require(all(record["one_cpu"][when]["affinity_count"] == 1 for when in ("metadata", "metadata_after")), prefix + "one-CPU witness absent")
        require(all(record["cpu_pressure"][when]["affinity_count"] == record["preflight"][when]["affinity_count"] for when in ("metadata", "metadata_after")), prefix + "pressure changed affinity")
        require(set(record["samples"]) == set(cases) and set(record["decisions"]) == set(cases), prefix + "case inventory")
        order = record["execution_order"]
        require(len(order) == 93 and set(map(tuple, order)) == {(i, case) for i in range(3) for case in cases}, prefix + "operation order")
        recomputed[allocation] = {}
        for case in cases:
            samples = record["samples"][case]
            require(len(samples) == 3, prefix + case + " repetitions")
            for repeat, sample in enumerate(samples):
                wait = expected_wait(case, repeat, contract)
                require(sample.get("verified") is True and type(sample.get("wall_ns")) is int and sample["wall_ns"] > 0 and sample["wall_ns"] >= wait, prefix + case + " duration/output")
                require(sample["injected_wait_ns"] == wait, prefix + case + " wait metadata")
                expected_claims = {"budget_ns": 10**15, "elapsed_ns": 1, "profile": "unlimited"} if case.endswith("/override_wait") else None
                require(sample["candidate_claims"] == expected_claims, prefix + case + " claims")
            decision = accept.evaluate(case.split("/")[0], [s["wall_ns"] for s in samples], record["admission"], contract, samples[0]["candidate_claims"])
            require(decision == record["decisions"][case], prefix + case + " recomputed decision mismatch")
            require(decision["verdict"] != "invalid_evidence", prefix + case + " invalid evidence")
            recomputed[allocation][case] = decision
        require(record["finished_unix_ns"] > record["started_unix_ns"], prefix + "harness timestamps")

    profiles = {}
    for profile in (CORE, SYNC):
        admitted = [r["allocation"] for r in records if r["admission"][profile]]
        profiles[profile] = {"preflight_admitted_ids": admitted, "preflight_rejected_ids": [r["allocation"] for r in records if not r["admission"][profile]], "availability_screen_pass": len(admitted) >= 23,
            "postflight_admitted_ids": [r["allocation"] for r in records if r["postflight_admission"][profile]],
            "preflight_admitted_then_postflight_rejected_ids": [r["allocation"] for r in records if r["admission"][profile] and not r["postflight_admission"][profile]],
            "pressure_rejected_ids": [r["allocation"] for r in records if not r["cpu_pressure_admission"][profile]],
            "one_cpu_rejected_ids": [r["allocation"] for r in records if not r["one_cpu_admission"][profile]]}
    case_results = {}
    for case in cases:
        op = case.split("/")[0]
        budget, profile = operations[op]["budget_ns"], operations[op]["profile"]
        ids = profiles[profile]["preflight_admitted_ids"]
        decisions = [recomputed[i][case] for i in ids]
        verdict_ids = {v: [r["allocation"] for r in records if recomputed[r["allocation"]][case]["verdict"] == v] for v in VERDICTS}
        raw = [s["wall_ns"] / 1e6 for r in records for s in r["samples"][case]]
        case_results[case] = {"budget_ms": budget / 1e6, "profile": profile, "admitted_count": len(ids), "verdict_ids": verdict_ids,
            "counts": {k: len(v) for k, v in verdict_ids.items()}, "all_raw_ms": summary(raw),
            "admitted_raw_ms": summary([s["wall_ns"] / 1e6 for r in records if r["allocation"] in ids for s in r["samples"][case]]),
            "minimum_would_pass_ids": [i for i in ids if recomputed[i][case]["raw_min_ns"] <= budget],
            "mean_would_pass_ids": [i for i in ids if recomputed[i][case]["raw_mean_ns"] <= budget],
            "minimum_would_hide_miss_ids": [i for i in ids if recomputed[i][case]["raw_min_ns"] <= budget and recomputed[i][case]["verdict"] != "pass"],
            "admitted_all_pass": bool(ids) and all(d["verdict"] == "pass" for d in decisions),
            "admitted_all_block": bool(ids) and all(d["verdict"] in ("mixed_miss", "all_over") for d in decisions)}
    specials = ["policy16_p1/periodic_wait", "policy16_p1/override_wait", "cycle48/cycle_wait"]
    controls = {case: {"admitted": case_results[case]["admitted_count"], "all_block": case_results[case]["admitted_all_block"], "minimum_hidden_ids": case_results[case]["minimum_would_hide_miss_ids"]} for case in specials}
    special_pass = all(row["all_block"] for row in controls.values())
    operation_results = {}
    for op, specification in operations.items():
        normal, wait = case_results[op + "/normal"], case_results[op + "/wait"]
        available = profiles[specification["profile"]]["availability_screen_pass"]
        operation_results[op] = {"budget_ms": specification["budget_ns"] / 1e6, "profile": specification["profile"],
            "admitted_count": normal["admitted_count"], "profile_available": available,
            "normal_all_pass": normal["admitted_all_pass"], "over_budget_wait_all_block": wait["admitted_all_block"],
            "usefulness_screen_pass": available and normal["admitted_all_pass"] and wait["admitted_all_block"] and special_pass,
            "normal_counts": normal["counts"], "normal_failure_ids": normal["verdict_ids"]["mixed_miss"] + normal["verdict_ids"]["all_over"],
            "normal_minimum_pass_count": len(normal["minimum_would_pass_ids"]), "normal_raw_ms": normal["all_raw_ms"]}
    costs = []
    for record in records:
        probes = {phase: sum(sum(v) for v in record[phase]["samples_ns"].values()) / 1e9 for phase in PHASES}
        product = sum(s["wall_ns"] for samples in record["samples"].values() for s in samples) / 1e9
        costs.append({"allocation": record["allocation"], "harness_seconds": (record["finished_unix_ns"] - record["started_unix_ns"]) / 1e9, "product_timed_seconds": product, "probe_timed_seconds": probes,
            "preflight_core_probe_seconds": sum(sum(record["preflight"]["samples_ns"][p]) for p in central.CORE_PROBES) / 1e9})
    probe_ranges = {phase: {name: summary([v / 1e6 for r in records for v in r[phase]["samples_ns"][name]]) for name in central.CAPS_NS} for phase in PHASES}
    return {"format": "all-absolute-budget-analysis/v4", "status": "finite_validation_not_policy_adoption", "source": collection["source"], "authority_revision": collection["authority_revision"], "run_id": collection["run_id"],
        "all_24_allocations_are_validation": True, "product_timings": 2232, "probe_timings": 1440, "total_timings": 3672,
        "contract": contract, "source_hashes": source_hashes, "profile_caps_ns": central.CAPS_NS, "profiles": profiles,
        "operations": operation_results, "cases": case_results, "special_controls": controls,
        "passing_operation_pairs": [op for op, row in operation_results.items() if row["usefulness_screen_pass"]],
        "pressure_rejection_screen_pass": len(profiles[CORE]["pressure_rejected_ids"]) >= 23,
        "one_cpu_rejection_screen_pass": len(profiles[CORE]["one_cpu_rejected_ids"]) == 24,
        "all_authority_boundary_checks_pass": True, "postflight_used_for_acceptance": False,
        "phase_admissions": phase_results, "probe_raw_ms": probe_ranges, "cost_observations": costs,
        "cost_seconds": {key: summary([c[key] for c in costs]) for key in ("harness_seconds", "product_timed_seconds", "preflight_core_probe_seconds")},
        "probe_cost_seconds": {phase: summary([c["probe_timed_seconds"][phase] for c in costs]) for phase in PHASES},
        "cpu_models": dict(Counter(r["preflight"]["metadata"]["cpu_model"] for r in records)),
        "image_versions": dict(Counter(r["preflight"]["metadata"]["image_version"] for r in records)),
        "kernels": dict(Counter(r["preflight"]["metadata"]["kernel"] for r in records))}


def render(result):
    ids = lambda xs: ", ".join(map(str, sorted(xs))) if xs else "none"
    name = lambda p: "sync" if p == SYNC else "core"
    lines = ["# #64 v4: raw wall-clock budgets and central profile admission", "",
        f'[Actions run](https://github.com/nashspence/all/actions/runs/{result["run_id"]}) at `{result["source"]}`; independent authority `{result["authority_revision"]}`. '
        "All 24 workers are fresh validation; no observations fit or adjust budgets, probe ceilings or acceptance. "
        "Retained evidence contains 2,232 product timings and 1,440 generic probe timings. Analysis recomputes all admissions and decisions from the pinned source and contract.", "",
        "## Profile availability and impairment controls", "",
        "| Profile | Preflight admitted /24 | Availability ≥23/24 | Postflight admitted /24 (diagnostic) | CPU-pressure rejected /24 | One-CPU rejected /24 |",
        "|---|---:|---|---:|---:|---:|"]
    for profile, row in result["profiles"].items():
        lines.append(f'| {name(profile)} | {len(row["preflight_admitted_ids"])} | {"pass" if row["availability_screen_pass"] else "fail"} | {len(row["postflight_admitted_ids"])} | {len(row["pressure_rejected_ids"])} | {len(row["one_cpu_rejected_ids"])} |')
    lines += ["", f'CPU-pressure sensitivity screen: **{"pass" if result["pressure_rejection_screen_pass"] else "fail"}**. '
        f'One-CPU rejection screen: **{"pass" if result["one_cpu_rejection_screen_pass"] else "fail"}**. '
        "A busy worker satisfying every fixed ceiling still satisfies the declared profile. Postflight and later impairment results never rewrite preflight admission or product verdicts.", "",
        "## Fixed raw operation budgets", "",
        "Every one of the three raw observations must fit B. Mixed misses block acceptance. Minimum is shown only to reveal observations that a minimum-based rule would hide.", "",
        "| Operation | B ms | Profile | Admitted | Strict pass | Mixed miss | All over | Unqualified | Minimum would pass | Usefulness screen |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---|"]
    for op, row in result["operations"].items():
        count = row["normal_counts"]
        lines.append(f'| {op} | {row["budget_ms"]:g} | {name(row["profile"])} | {row["admitted_count"]} | {count["pass"]} | {count["mixed_miss"]} | {count["all_over"]} | {count["unqualified"]} | {row["normal_minimum_pass_count"]} | {"pass" if row["usefulness_screen_pass"] else "fail"} |')
    passing = result["passing_operation_pairs"]
    lines += ["", f'Passing operation/profile pairs: **{len(passing)}/11**. ' + (", ".join(passing) if passing else "None."), "",
        "A failed row is not repaired by adjusting B or dropping workers. An admitted raw miss is a measured budget miss, not proof of its cause. Resource admission and actual operation conformance are separate claims.", "",
        "## All additional cases", "",
        "Wait means an actual B+16 ms delay; extra50 means additional processing and may legitimately pass an absolute budget. Periodic wait affects one repetition; cycle wait lies inside every complete cycle. All values below use binding preflight admission.", "",
        "| Case | Pass | Mixed miss | All over | Unqualified | Minimum would hide miss |",
        "|---|---:|---:|---:|---:|---:|"]
    for case, row in result["cases"].items():
        if case.endswith("/normal"):
            continue
        c = row["counts"]
        lines.append(f'| {case} | {c["pass"]} | {c["mixed_miss"]} | {c["all_over"]} | {c["unqualified"]} | {len(row["minimum_would_hide_miss_ids"])} |')
    lines += ["", "Every record confirms the candidate manifest was actually changed, the separate authority remained unchanged, proposed budgets did not activate, and later probes could not rewrite decisions. The override case's fabricated elapsed time/profile/budget are rejected while the trusted outer clock remains decisive. This demonstrates the experiment's source boundary; real repository approval permissions still require their normal protected-review arrangement.", "",
        "The candidate adapter is imported and its fixtures are constructed before preflight. Preflight precedes the timed product calls, not all candidate code. The adapter also executes in the timer's Python process: this is not isolation against arbitrary candidate code or monkeypatching. The tested controls cover ordinary manifest/claim overrides; owning-contract review must still bind fixtures, entrypoints and completion to the intended operation.", "",
        "## Failure and unavailability IDs", ""]
    for profile, row in result["profiles"].items():
        lines.append(f'- {name(profile)} preflight rejected: {ids(row["preflight_rejected_ids"])}. Preflight admitted then postflight rejected: {ids(row["preflight_admitted_then_postflight_rejected_ids"])}.')
    lines += ["", "| Case | Mixed-miss IDs | All-over IDs |", "|---|---|---|"]
    for case, row in result["cases"].items():
        if case.endswith(("/normal", "/extra50")):
            mixed, over = row["verdict_ids"]["mixed_miss"], row["verdict_ids"]["all_over"]
            if mixed or over:
                lines.append(f'| {case} | {ids(mixed)} | {ids(over)} |')
    for case, row in result["cases"].items():
        if case.endswith(("/wait", "/periodic_wait", "/override_wait", "/cycle_wait")) and row["verdict_ids"]["pass"]:
            lines.append(f'Unexpected negative-control passes for {case}: {ids(row["verdict_ids"]["pass"])}.')
    lines += ["", "Full per-case verdict IDs, all admission reasons and probe ranges are retained in analysis.json; all raw samples remain in observations.json. Unqualified cohorts are unavailable evidence, not passes.", "",
        "## Raw unchanged timing and measurement cost", "",
        "All raw samples, including nonadmitted workers, are included in these ranges. These are complete declared observations; a 512-check window is not a cold 16-member latency estimate.", "",
        "| Operation | Raw min ms | Raw max ms |", "|---|---:|---:|"]
    for op, row in result["operations"].items():
        raw = row["normal_raw_ms"]
        lines.append(f'| {op} | {raw["minimum"]:.3f} | {raw["maximum"]:.3f} |')
    costs, probes = result["cost_seconds"], result["probe_cost_seconds"]
    lines += ["", f'Sum of timed preflight probe calls: median {probes["preflight"]["median"]:.2f}s (core-only calls {costs["preflight_core_probe_seconds"]["median"]:.2f}s); this excludes probe preparation and verification. '
        f'Whole experimental harness: median {costs["harness_seconds"]["median"]:.2f}s, range {costs["harness_seconds"]["minimum"]:.2f}–{costs["harness_seconds"]["maximum"]:.2f}s, excluding Actions setup/upload. '
        "The full diagnostic campaign also performs postflight, CPU-pressure and one-CPU controls; these are not proposed per-operation overhead.", "",
        "## Scope and reproduction", "",
        "These are experimental numbers, not approved product budgets. The experiment does not fit tolerances, normalize time, use a project reference implementation, or establish physical durability. Parallel wrappers and the process-start case are experimental adapters. A passing case establishes this finite raw-budget procedure on sampled workers, not universal or tail-latency bounds, future-image reliability, or Riverhog/Fishhat performance.", "",
        "Run `python experiments/64/v4/analyze.py` against retained observations to reproduce this report. Source/hash, contract, runtime, observation completeness, authority mutation, fixed-wait and exact acceptance checks run before summary generation. No new workers are launched.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE / "observations.json")
    args = parser.parse_args()
    result = analyze(json.loads(args.source.read_text()))
    (HERE / "analysis.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    (HERE / "RESULTS.md").write_text(render(result))
    print(json.dumps({"run_id": result["run_id"], "passing_operation_pairs": result["passing_operation_pairs"], "timings": result["total_timings"]}))


if __name__ == "__main__":
    main()
