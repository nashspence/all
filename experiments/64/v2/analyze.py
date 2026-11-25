#!/usr/bin/env python3
"""Reproduce the predeclared v2 paired-reference calibration screens."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import statistics


BASE = "03de186a044c9c6b365347485a6c4093ce831c79"
FIXTURE = "e2b3a325c2656969cc88573c78f625d0ae1d08578227fef4c6092de71123bf5a"
PROTOCOL = "967e0c485c3ea2f50c82cc16f3971ca1c276182eda929299cf53e37b20cffc8a"
WAIT_NS = 64_000_000
CAP = 0.20
HEADROOM = 0.03
BUDGET_RATIO = 1.20
BASE_FAMILIES = [f"policy{n}_p{p}" for n in (16, 512) for p in (1, 2, 4)] + ["files4096", "sqlite64"]
CASES = [f"{family}/{mode}" for family in BASE_FAMILIES for mode in ("same", "work50")]
CASES += [f"policy16_p1/{mode}" for mode in ("wait_each", "wait_once", "reference_wait_once", "reference_wait_each")]
CASES += ["cycle48/same", "cycle48/wait_cycle", "cold16/same", "cold16/wait_each"]
FAMILIES = BASE_FAMILIES + ["cycle48", "cold16"]
ESTIMATORS = {"minimum": min, "first": lambda xs: xs[0], "mean": statistics.mean, "median": statistics.median}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def positive_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value < float("inf")


def expected_wait(case, role, repeat):
    family, mode = case.split("/")
    if role == "candidate" and (mode in ("wait_each", "wait_cycle") or mode == "wait_once" and repeat == 1):
        return WAIT_NS
    if role == "reference" and (mode == "reference_wait_each" or mode == "reference_wait_once" and repeat == 1):
        return WAIT_NS
    return 0


def validate(source):
    require(source.get("complete") is True, "collection is incomplete")
    require(re.fullmatch(r"[0-9a-f]{40}", source.get("source", "")), "missing exact experiment source")
    records = sorted(source["records"], key=lambda r: r["allocation"])
    require([r["allocation"] for r in records] == list(range(1, 25)), "need exactly allocations 1-24")
    require(str(source.get("run_attempt", 1)) == "1", "unexpected rerun attempt")
    for record in records:
        allocation = record["allocation"]
        require(record.get("format") == "all-paired-calibration/v2", f"allocation {allocation}: format")
        require(record.get("source") == source["source"] and record.get("frozen_source") == BASE, f"allocation {allocation}: source")
        require(str(record.get("run_id")) == str(source.get("run_id")) and str(record.get("run_attempt")) == "1", f"allocation {allocation}: run")
        require(record.get("fixture_sha256") == FIXTURE and record.get("protocol_sha256") == PROTOCOL, f"allocation {allocation}: fixture/protocol hash")
        require(record.get("verified") is True and record.get("smoke") is False, f"allocation {allocation}: unverified or smoke")
        require(record.get("phase") == ("fit" if allocation <= 12 else "holdout"), f"allocation {allocation}: phase")
        env = record["environment"]
        require(env["python"] == "3.11.9" and env["yaml"] == "6.0.3", f"allocation {allocation}: runtime")
        require(env["logical_cpus"] == 4 and env["affinity_count"] == 4, f"allocation {allocation}: CPU allocation")
        require(set(record["samples"]) == set(CASES), f"allocation {allocation}: cases")
        for case, values in record["samples"].items():
            require(set(values) == {"reference", "candidate"}, f"allocation {allocation}: roles")
            for role, samples in values.items():
                require(len(samples) == 3, f"allocation {allocation}: repetition count")
                for repeat, sample in enumerate(samples):
                    require(positive_number(sample["wall_ns"]), f"allocation {allocation}: duration")
                    require(sample["injected_wait_ns"] == expected_wait(case, role, repeat), f"allocation {allocation}: wait metadata")
                    require(sample["wall_ns"] >= sample["injected_wait_ns"], f"allocation {allocation}: truncated wait")
        order = record["execution_order"]
        require(len(order) == 144, f"allocation {allocation}: order length")
        expected = {(repeat, case, role) for repeat in range(3) for case in CASES for role in ("reference", "candidate")}
        require(set(map(tuple, order)) == expected, f"allocation {allocation}: order members")
        for first, second in zip(order[::2], order[1::2]):
            require(first[:2] == second[:2] and first[2] != second[2], f"allocation {allocation}: nonadjacent pair")
        require(record["finished_unix_ns"] > record["started_unix_ns"], f"allocation {allocation}: harness timestamps")
    # The collector should add API runner/job IDs. If absent, keep the limitation explicit.
    for key in ("runner_id", "job_id"):
        present = [record.get(key) for record in records]
        if any(value is not None for value in present):
            require(all(value is not None for value in present) and len(set(present)) == 24, f"duplicate/missing {key}")
    return records


def spread(values):
    return {"minimum": min(values), "median": statistics.median(values), "mean": statistics.mean(values), "maximum": max(values)}


def classify(ratio, error):
    if error >= 1:
        return {"lower": None, "upper": None, "band_classification": "unestablished"}
    lower, upper = ratio / (1 + error), ratio / (1 - error)
    return {"lower": lower, "upper": upper,
            "band_classification": "pass" if upper <= BUDGET_RATIO else "miss" if lower > BUDGET_RATIO else "overlap"}


def analyse(source):
    records = validate(source)
    all_results = {}
    for name, estimator in ESTIMATORS.items():
        estimates = {case: [{"allocation": r["allocation"], "phase": r["phase"],
                            "reference_ms": estimator([s["wall_ns"] for s in r["samples"][case]["reference"]]) / 1e6,
                            "candidate_ms": estimator([s["wall_ns"] for s in r["samples"][case]["candidate"]]) / 1e6}
                           for r in records] for case in CASES}
        for rows in estimates.values():
            for row in rows:
                row["ratio"] = row["candidate_ms"] / row["reference_ms"]
        family_results = {}
        for family in FAMILIES:
            same = estimates[f"{family}/same"]
            fit, held = same[:12], same[12:]
            fit_error = max(abs(row["ratio"] - 1) for row in fit)
            allowance = fit_error + HEADROOM
            anchor = statistics.median(row["reference_ms"] for row in fit)
            held_error = max(abs(row["ratio"] - 1) for row in held)
            outside = [row["allocation"] for row in held if abs(row["ratio"] - 1) > allowance]
            qualified = allowance <= CAP and not outside
            family_result = {
                "reference_anchor_ms": anchor, "fit_max_null_error": fit_error,
                "allowance": allowance, "allowance_within_cap": allowance <= CAP,
                "heldout_max_null_error": held_error, "heldout_outside_allowance": outside,
                "finite_null_screen_pass": qualified,
                "raw_null_reference_ms": spread([row["reference_ms"] for row in same]),
                "raw_null_candidate_ms": spread([row["candidate_ms"] for row in same]),
                "all_null_ratios": spread([row["ratio"] for row in same]),
                "heldout_null_ratios": spread([row["ratio"] for row in held]),
            }
            for case, rows in estimates.items():
                if case.split("/")[0] != family:
                    continue
                for row in rows:
                    row.update(classify(row["ratio"], allowance))
                    row["reference_equivalent_ms"] = anchor * row["ratio"]
                    row["qualified_classification"] = row["band_classification"] if qualified else "unestablished"
            family_result["heldout_null_band_pass_count"] = sum(row["band_classification"] == "pass" for row in held)
            family_result["heldout_null_qualified_pass_count"] = sum(row["qualified_classification"] == "pass" for row in held)
            if family in BASE_FAMILIES:
                work = estimates[f"{family}/work50"][12:]
                family_result.update({
                    "heldout_work50_ratios": spread([row["ratio"] for row in work]),
                    "heldout_work50_sensitivity_pass_count": sum(row["ratio"] > BUDGET_RATIO for row in work),
                    "sensitivity_screen_pass": all(row["ratio"] > BUDGET_RATIO for row in work),
                    "heldout_work50_band_miss_count": sum(row["band_classification"] == "miss" for row in work),
                    "heldout_work50_qualified_miss_count": sum(row["qualified_classification"] == "miss" for row in work),
                    "stronger_null_pass_and_work_miss_screen": qualified and all(row["band_classification"] == "pass" for row in held)
                        and all(row["band_classification"] == "miss" for row in work),
                })
            family_results[family] = family_result
        case_results = {}
        for case, rows in estimates.items():
            held = rows[12:]
            case_results[case] = {
                "all_ratios": spread([row["ratio"] for row in rows]),
                "heldout_ratios": spread([row["ratio"] for row in held]),
                "heldout_above_1_20_count": sum(row["ratio"] > BUDGET_RATIO for row in held),
                "heldout_band_classifications": dict(Counter(row["band_classification"] for row in held)),
                "heldout_qualified_classifications": dict(Counter(row["qualified_classification"] for row in held)),
                "raw_reference_ms": spread([row["reference_ms"] for row in rows]),
                "raw_candidate_ms": spread([row["candidate_ms"] for row in rows]),
                "observations": rows,
            }
        scaling = {}
        for extent in (16, 512):
            for workers in (2, 4):
                for role in ("reference", "candidate"):
                    serial = estimates[f"policy{extent}_p1/same"]
                    parallel = estimates[f"policy{extent}_p{workers}/same"]
                    values = [s[f"{role}_ms"] / p[f"{role}_ms"] for s, p in zip(serial, parallel)]
                    scaling[f"policy{extent}_p{workers}/{role}"] = spread(values)
        all_results[name] = {"families": family_results, "cases": case_results, "same_worker_scaling": scaling}
    # Deliberately unsafe alternative: small C/R can result from a slow reference.
    denominator_diagnostic = {}
    for case in ("policy16_p1/same", "policy16_p1/reference_wait_once", "policy16_p1/reference_wait_each"):
        rows = []
        for record in records:
            samples = record["samples"][case]
            refs = [s["wall_ns"] for s in samples["reference"]]
            candidates = [s["wall_ns"] for s in samples["candidate"]]
            chosen = min(range(3), key=lambda i: candidates[i] / refs[i])
            rows.append({"allocation": record["allocation"], "ratio_of_minima": min(candidates) / min(refs),
                         "minimum_of_pair_ratios": candidates[chosen] / refs[chosen], "chosen_repeat": chosen,
                         "selected_reference_over_its_minimum": refs[chosen] / min(refs)})
        denominator_diagnostic[case] = {"observations": rows,
            "ratio_of_minima": spread([row["ratio_of_minima"] for row in rows]),
            "minimum_of_pair_ratios": spread([row["minimum_of_pair_ratios"] for row in rows])}
    hardware = defaultdict(list)
    for record in records:
        hardware[record["environment"]["cpu_model"]].append(record["allocation"])
    harness = []
    for record in records:
        elapsed_ms = (record["finished_unix_ns"] - record["started_unix_ns"]) / 1e6
        timed_ms = sum(s["wall_ns"] for sides in record["samples"].values() for samples in sides.values() for s in samples) / 1e6
        harness.append({"allocation": record["allocation"], "elapsed_ms": elapsed_ms, "timed_ms": timed_ms,
                        "outside_timers_ms": elapsed_ms - timed_ms})
    return {
        "format": "all-paired-calibration-analysis/v2", "status": "finite_experiment_not_policy_adoption",
        "source": source["source"], "run_id": source["run_id"], "frozen_source": BASE,
        "expected_allocations": 24, "complete": True, "verified_timing_observations": 24 * 24 * 2 * 3,
        "unique_runner_ids": len({r["runner_id"] for r in records}) if all("runner_id" in r for r in records) else None,
        "primary_estimator": "minimum", "fit_allocations": list(range(1, 13)), "holdout_allocations": list(range(13, 25)),
        "maximum_allowance": CAP, "headroom": HEADROOM, "illustrative_budget_ratio": BUDGET_RATIO,
        "decisions": all_results, "denominator_contamination_diagnostic": denominator_diagnostic,
        "cpu_models": dict(hardware), "image_versions": dict(Counter(r["environment"]["image_version"] for r in records)),
        "kernels": dict(Counter(r["environment"]["kernel"] for r in records)),
        "harness_observations": harness, "harness_elapsed_ms": spread([r["elapsed_ms"] for r in harness]),
        "timed_ms": spread([r["timed_ms"] for r in harness]),
        "fit_completed_before_holdout_started_by_host_timestamps": max(r["finished_unix_ns"] for r in records[:12]) <= min(r["started_unix_ns"] for r in records[12:]),
        "limitations": [
            "Finite heldout screen, not a statistical confidence interval or long-term false-alarm estimate.",
            "Both waves occur in one short campaign; weekly image or future workload transfer is unqualified.",
            "Minimum is the primary estimator; other estimators are diagnostics, not post-hoc promoted winners.",
            "Experimental fit reference anchors and 1.20 budget ratio are not adopted operator usability targets.",
            "Process-pool parallelism and process-cold wrapper are experimental, not supported product modes.",
            "SQLite FULL API timings are not physical persistence or power-loss qualification.",
            "Reference and candidate share pinned runtime/dependency versions; upgrades require independently packaged reference dependencies.",
            "Reference/candidate mixtures can diverge; periodic product cost can vanish from minimum estimates.",
        ],
    }


def render(result):
    primary = result["decisions"]["minimum"]
    lines = ["# #64 paired-reference calibration: v2 results", "",
             f'[Actions run](https://github.com/nashspence/all/actions/runs/{result["run_id"]}) at `{result["source"]}`. '
             f'24 complete allocations, 24 case combinations, three adjacent reference/candidate pairs: **{result["verified_timing_observations"]:,} verified timings**. '
             "The primary estimator and thresholds were declared before collection in PLAN.md. "
             "This is a finite experiment, not policy adoption or Riverhog/Fishhat qualification.", "",
             "## Primary: minimum candidate / minimum reference", "",
             "Fit IDs 1–12 define e = maximum A/A deviation from 1 + 3 percentage points, capped at 20%. "
             "Every heldout A/A ratio (IDs 13–24) must remain inside that fixed allowance. "
             "Sensitivity independently requires every heldout +50%-work ratio >1.20. No timing was removed or recentered.", "",
             "| Workload | Fit max A/A error | e | Holdout max A/A error | Null screen | +50% work >1.20 | Null budget pass | Work budget miss |",
             "|---|---:|---:|---:|---|---:|---:|---:|"]
    for family, row in primary["families"].items():
        lines.append(f'| {family} | {row["fit_max_null_error"]:.1%} | {row["allowance"]:.1%} | '
                     f'{row["heldout_max_null_error"]:.1%} | {"pass" if row["finite_null_screen_pass"] else "fail"} | '
                     f'{str(row["heldout_work50_sensitivity_pass_count"])+"/12" if "heldout_work50_sensitivity_pass_count" in row else "n/a"} | '
                     f'{row["heldout_null_qualified_pass_count"]}/12 | '
                     f'{str(row["heldout_work50_qualified_miss_count"])+"/12" if "heldout_work50_qualified_miss_count" in row else "n/a"} |')
    lines += ["", "The final two columns use qualified conservative bands against an illustrative budget of 1.20 reference units: "
              "upper=ratio/(1−e) must be ≤1.20 for pass; lower=ratio/(1+e) must exceed 1.20 for miss. "
              "A failed null calibration leaves qualification unestablished even if an arithmetic band looks favorable.", "",
              "## Estimator diagnostics (same predeclared screen)", "",
              "These are diagnostics. Selecting a different estimator after viewing these results requires new validation.", "",
              "| Estimator | Families passing null screen /10 | Added-work families passing sensitivity /8 | Families passing both /8 | Stronger conservative screen /8 |",
              "|---|---:|---:|---:|---:|"]
    for name, decision in result["decisions"].items():
        families = decision["families"]
        null = sum(row["finite_null_screen_pass"] for row in families.values())
        sensitive = sum(families[f]["sensitivity_screen_pass"] for f in BASE_FAMILIES)
        both = sum(families[f]["finite_null_screen_pass"] and families[f]["sensitivity_screen_pass"] for f in BASE_FAMILIES)
        strong = sum(families[f]["stronger_null_pass_and_work_miss_screen"] for f in BASE_FAMILIES)
        lines.append(f"| {name} | {null}/10 | {sensitive}/8 | {both}/8 | {strong}/8 |")
    lines += ["", "## Raw and reference-equivalent timing", "",
              "These reference anchors are the median of fit workers' minimum reference times, fixed for interpreting the holdout. "
              "They provide reference-equivalent units: anchor × candidate/reference. They are not fixed-hardware latency claims or authoritative budgets. "
              "All times below are milliseconds for the full named observation.", "",
              "| Family | Experimental anchor ms | Raw null reference min–max ms | Raw null candidate min–max ms |",
              "|---|---:|---:|---:|"]
    for family, row in primary["families"].items():
        ref, cand = row["raw_null_reference_ms"], row["raw_null_candidate_ms"]
        lines.append(f'| {family} | {row["reference_anchor_ms"]:.3f} | {ref["minimum"]:.3f}–{ref["maximum"]:.3f} | {cand["minimum"]:.3f}–{cand["maximum"]:.3f} |')
    lines += ["", "## Wait and denominator diagnostics", "",
              "Each injection adds 64 ms of actual timed waiting. The one-off wait is the middle repeat; the full-cycle case includes one wait in every complete three-operation window. "
              "The ratio below is the median across all 24 allocation ratios. No added wait is subtracted.", "",
              "| Case | Minimum ratio | Mean ratio | Median ratio | First ratio |",
              "|---|---:|---:|---:|---:|"]
    for case in ("policy16_p1/wait_each", "policy16_p1/wait_once", "policy16_p1/reference_wait_once", "policy16_p1/reference_wait_each", "cycle48/wait_cycle", "cold16/wait_each"):
        ratios = [result["decisions"][name]["cases"][case]["all_ratios"]["median"] for name in ("minimum", "mean", "median", "first")]
        lines.append(f'| {case} | ' + ' | '.join(f"{ratio:.3f}" for ratio in ratios) + ' |')
    lines += ["", "| Denominator case | Ratio of minima median | Minimum of pair ratios median |", "|---|---:|---:|"]
    for case, row in result["denominator_contamination_diagnostic"].items():
        lines.append(f'| {case} | {row["ratio_of_minima"]["median"]:.3f} | {row["minimum_of_pair_ratios"]["median"]:.3f} |')
    lines += ["", "A fast minimum cannot establish typical or tail latency. A minimum ratio can be falsely reduced by a slow reference; "
              "a persistently contaminated reference can also corrupt the ratio of minima. These controls diagnose the limitation rather than authorize discarding workers.", "",
              "## Same-worker scaling", "",
              "Experimental outer pool; no product parallelism claim. Startup and shutdown remain timed.", "",
              "| Case/role | Median T1/Tp | Range |", "|---|---:|---:|"]
    for case, row in primary["same_worker_scaling"].items():
        lines.append(f'| {case} | {row["median"]:.3f}× | {row["minimum"]:.3f}–{row["maximum"]:.3f}× |')
    elapsed = result["harness_elapsed_ms"]
    lines += ["", "## Environment and cost", "",
              f'24 allocations; verified unique runner IDs: {result["unique_runner_ids"]}. '
              f'Harness elapsed per allocation: median {elapsed["median"]/1000:.2f}s, range {elapsed["minimum"]/1000:.2f}–{elapsed["maximum"]/1000:.2f}s. '
              "This excludes Actions checkout/setup/upload. Detailed elapsed and timed totals are retained in analysis.json.", "",
              "| CPU model | Allocations |", "|---|---|"]
    for model, ids in result["cpu_models"].items():
        lines.append(f'| {model} | {", ".join(map(str, ids))} |')
    lines += ["", "## Limits and reproduction", ""]
    lines += [f"- {limitation}" for limitation in result["limitations"]]
    lines += ["", "Run `python experiments/64/v2/analyze.py` from the repository checkout. "
              "The script validates completeness, source and fixture identities, runtime, counts, correct-output flags, "
              "injected waits and adjacency before writing analysis.json and this report. "
              "The raw observations remain authoritative; workflow success only establishes successful measurement collection.", ""]
    return "\n".join(lines)


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=here / "observations.json")
    parser.add_argument("--output", type=Path, default=here / "analysis.json")
    parser.add_argument("--report", type=Path, default=here / "RESULTS.md")
    args = parser.parse_args()
    result = analyse(json.loads(args.source.read_text()))
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    args.report.write_text(render(result))
    print(json.dumps({"complete": True, "run_id": result["run_id"], "output": str(args.output), "report": str(args.report),
                      "primary_null_screens_passed": sum(r["finite_null_screen_pass"] for r in result["decisions"]["minimum"]["families"].values())}))


if __name__ == "__main__":
    main()
