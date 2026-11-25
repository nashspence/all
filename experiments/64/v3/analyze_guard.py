#!/usr/bin/env python3
"""Validate the predeclared v3 reference guard; never refit from fresh data."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("v2_analyzer", HERE.parent / "v2/analyze.py")
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


def spread(values):
    return None if not values else {"minimum": min(values), "median": statistics.median(values), "maximum": max(values)}


def analyze(source, config):
    records = v2.validate(source)
    v2.require(config["format"] == "all-reference-guard-config/v3", "wrong guard configuration")
    v2.require(config["fitted_from"]["source"] == "7355aed8042e61eedc491428a063080a7f557f5b", "wrong fit source")
    v2.require(config["fitted_from"]["run_id"] == 45680767861, "wrong fit run")
    v2.require(source["run_id"] != config["fitted_from"]["run_id"], "fresh validation must not reuse fitted run")
    v2.require(config["guard_maximum_symmetric_relative_difference"] == 0.10 and config["maximum_allowance"] == 0.20,
               "guard/cap changed from predeclaration")
    v2.require(config["illustrative_budget_ratio"] == 1.20 and config["minimum_guard_eligible_per_cohort"] == 23,
               "budget/availability changed from predeclaration")
    v2.require(set(config["families"]) == set(v2.FAMILIES), "family configuration mismatch")
    primary = ["policy16_p1", "policy512_p1", "policy512_p2", "policy512_p4", "files4096"]
    v2.require(config["primary_families"] == primary, "primary family selection changed")
    for family, item in config["families"].items():
        v2.require(abs(item["allowance"] - item["fit_max_null_error_all_24"] - 0.03) < 1e-12, "allowance changed")
        v2.require(item["reference_anchor_ms"] > 0, "invalid anchor")
    cases = {}
    for case in v2.CASES:
        family, mode = case.split("/")
        item = config["families"][family]
        audit_case = item["same_case_audit"] if mode == "same" else family + "/same"
        allowance = item["allowance"]
        rows = []
        for record in records:
            minimum = lambda c, role: min(s["wall_ns"] for s in record["samples"][c][role])
            ref, audit, candidate = minimum(case, "reference"), minimum(audit_case, "reference"), minimum(case, "candidate")
            denominator = min(ref, audit)
            guard = max(ref, audit) / denominator - 1
            eligible = guard <= 0.10
            score = candidate / denominator
            band = v2.classify(score, allowance)
            classification = band["band_classification"] if eligible and allowance <= 0.20 else "unestablished"
            rows.append({"allocation": record["allocation"], "reference_guard": guard, "guard_eligible": eligible,
                         "score": score, "within_fixed_null_allowance": abs(score - 1) <= allowance,
                         "reference_equivalent_ms": score * item["reference_anchor_ms"],
                         "reference_ms": ref / 1e6, "audit_reference_ms": audit / 1e6, "candidate_ms": candidate / 1e6,
                         "classification": classification, "arithmetic_band_classification": band["band_classification"]})
        admitted = [row for row in rows if row["guard_eligible"]]
        cases[case] = {
            "audit_case": audit_case, "allowance": allowance, "allowance_within_cap": allowance <= 0.20,
            "eligible_count": len(admitted), "eligible_allocations": [r["allocation"] for r in admitted],
            "ineligible_allocations": [r["allocation"] for r in rows if not r["guard_eligible"]],
            "eligible_null_allowance_misses": [r["allocation"] for r in admitted if not r["within_fixed_null_allowance"]],
            "eligible_nonpass_allocations": [r["allocation"] for r in admitted if r["classification"] != "pass"],
            "eligible_nonmiss_allocations": [r["allocation"] for r in admitted if r["classification"] != "miss"],
            "qualified_classifications": dict(Counter(r["classification"] for r in rows)),
            "all_guard_range": spread([r["reference_guard"] for r in rows]),
            "all_score_range": spread([r["score"] for r in rows]),
            "eligible_score_range": spread([r["score"] for r in admitted]),
            "all_candidate_ms": spread([r["candidate_ms"] for r in rows]),
            "all_reference_ms": spread([r["reference_ms"] for r in rows]),
            "exceptional_observations": [r for r in rows if not r["guard_eligible"] or (mode == "same" and
                (not r["within_fixed_null_allowance"] or r["classification"] != "pass")) or
                (mode in ("work50", "wait_each", "wait_cycle") and r["classification"] != "miss")],
        }
    families = {}
    for family, item in config["families"].items():
        null = cases[family + "/same"]
        row = {"primary": family in primary, "allowance": item["allowance"],
               "reference_anchor_ms": item["reference_anchor_ms"], "allowance_within_cap": item["allowance"] <= 0.20,
               "null_guard_eligible_count": null["eligible_count"],
               "null_guard_available": null["eligible_count"] >= 23,
               "eligible_null_scores_within_fixed_allowance": not null["eligible_null_allowance_misses"],
               "eligible_null_all_pass": bool(null["eligible_count"]) and not null["eligible_nonpass_allocations"]}
        row["reference_reproducibility_pass"] = row["allowance_within_cap"] and row["null_guard_available"] and row["eligible_null_scores_within_fixed_allowance"]
        row["null_screen_pass"] = row["reference_reproducibility_pass"] and row["eligible_null_all_pass"]
        if family in v2.BASE_FAMILIES:
            work = cases[family + "/work50"]
            row.update({"work_guard_eligible_count": work["eligible_count"], "work_guard_available": work["eligible_count"] >= 23,
                        "eligible_work_all_miss": bool(work["eligible_count"]) and not work["eligible_nonmiss_allocations"]})
            row["strong_family_pass"] = row["null_screen_pass"] and row["work_guard_available"] and row["eligible_work_all_miss"]
        families[family] = row
    persistent = cases["policy16_p1/reference_wait_each"]
    once = cases["policy16_p1/reference_wait_once"]
    cycle = cases["cycle48/wait_cycle"]
    diagnostics = {
        "persistent_reference_delay": {"rejected_count": len(persistent["ineligible_allocations"]),
                                       "pass": persistent["eligible_count"] == 0},
        "single_reference_delay": {"eligible_count": once["eligible_count"],
                                   "eligible_null_allowance_misses": once["eligible_null_allowance_misses"],
                                   "eligible_nonpass_allocations": once["eligible_nonpass_allocations"],
                                   "pass": once["eligible_count"] >= 23 and not once["eligible_null_allowance_misses"] and not once["eligible_nonpass_allocations"]},
        "complete_cycle_wait": {"eligible_count": cycle["eligible_count"], "eligible_nonmiss_allocations": cycle["eligible_nonmiss_allocations"],
                                "pass": cycle["eligible_count"] >= 23 and not cycle["eligible_nonmiss_allocations"]},
    }
    return {"format": "all-reference-guard-analysis/v3", "status": "fresh_finite_validation_not_policy_adoption",
            "source": source["source"], "run_id": source["run_id"], "fit_run_id": config["fitted_from"]["run_id"],
            "validation_allocations": list(range(1, 25)), "verified_timings": 3456,
            "primary_families": primary, "primary_family_pass_count": sum(families[f]["strong_family_pass"] for f in primary),
            "primary_reference_reproducibility_pass_count": sum(families[f]["reference_reproducibility_pass"] for f in primary),
            "all_primary_families_pass": all(families[f]["strong_family_pass"] for f in primary),
            "all_adversarial_diagnostics_pass": all(d["pass"] for d in diagnostics.values()),
            "families": families, "cases": cases, "diagnostics": diagnostics,
            "cpu_models": dict(Counter(r["environment"]["cpu_model"] for r in records)),
            "harness_elapsed_seconds": spread([(r["finished_unix_ns"] - r["started_unix_ns"]) / 1e9 for r in records]),
            "interpretation": [
                "Every allocation is fresh validation against coefficients frozen from all 24 v2 allocations.",
                "No v3 fit, recentering, allowance widening, estimator selection or post-hoc exclusions.",
                "Ineligible cohorts remain unestablished and count against declared availability.",
                "Null score mismatch is a failed calibration prediction, not an environmental rejection.",
                "A guard validates reference agreement, not reference equivalence to a physically fixed machine.",
                "Shared contamination of both references and changed candidate resource mixtures remain transfer limitations.",
                "Minimum still does not establish typical or tail latency; complete recurring work must lie inside every timed window.",
                "This short finite campaign cannot estimate long-term false-alarm probabilities or image-update transfer.",
            ]}


def render(result):
    lines = ["# #64 frozen reference guard: fresh v3 validation", "",
             f'[Actions run](https://github.com/nashspence/all/actions/runs/{result["run_id"]}) at `{result["source"]}`. '
             "All 24 allocations validate a fixed rule fitted from the previous v2 campaign. The old `fit`/`holdout` labels in raw records "
             "are harness metadata only; no fresh observations fit this rule. All 3,456 timings remain retained.", "",
             "## Fixed decision", "",
             "Reference agreement: max(Rcase,Raudit)/min(Rcase,Raudit)−1≤10%, using each reference's minimum of three. "
             "Score=min(candidate)/min(Rcase,Raudit). The faster reference is the denominator. "
             "The fixed error allowance and reference anchor are in guard_config.json; the allowance is never widened or clamped. "
             "At least 23/24 cohorts must be eligible in both unchanged and +50%-work cases. Every eligible unchanged score must "
             "remain within its fixed allowance and support a conservative pass against 1.20; every eligible work score must support a miss. "
             "A mismatch fails the screen; it is not discarded as noise.", "",
             "| Family | Scope | Fixed e | Eligible null /24 | Eligible work /24 | Reference reproducibility | All eligible null budget pass | All eligible work miss | Combined |",
             "|---|---|---:|---:|---:|---|---|---|---|"]
    for family, row in result["families"].items():
        lines.append(f'| {family} | {"primary" if row["primary"] else "secondary"} | {row["allowance"]:.1%} | '
                     f'{row["null_guard_eligible_count"]} | {row.get("work_guard_eligible_count", "n/a")} | '
                     f'{"pass" if row["reference_reproducibility_pass"] else "fail"} | '
                     f'{"yes" if row["eligible_null_all_pass"] else "no"} | '
                     f'{("yes" if row["eligible_work_all_miss"] else "no") if "eligible_work_all_miss" in row else "n/a"} | '
                     f'{("pass" if row["strong_family_pass"] else "fail") if "strong_family_pass" in row else "n/a"} |')
    lines += ["", f'Primary reference reproducibility: **{result["primary_reference_reproducibility_pass_count"]}/5 pass**. '
              f'Stronger combined budget/detection screen: **{result["primary_family_pass_count"]}/5 pass**. '
              "An overlap with the illustrative budget is distinct from failed reference reproducibility; it indicates insufficient budget headroom under this decision rule. "
              "Secondary failures do not become qualified by passing a primary family.", "",
              "## Adversarial checks", "",
              "| Check | Eligible/rejected result | Predeclared outcome |", "|---|---|---|"]
    d = result["diagnostics"]
    lines += [f'| Persistent reference-only delay | {d["persistent_reference_delay"]["rejected_count"]}/24 rejected | {"pass" if d["persistent_reference_delay"]["pass"] else "fail"} |',
              f'| One delayed reference repetition | {d["single_reference_delay"]["eligible_count"]}/24 eligible; {len(d["single_reference_delay"]["eligible_nonpass_allocations"])} eligible nonpasses | {"pass" if d["single_reference_delay"]["pass"] else "fail"} |',
              f'| Complete cycle with recurring wait | {d["complete_cycle_wait"]["eligible_count"]}/24 eligible; {len(d["complete_cycle_wait"]["eligible_nonmiss_allocations"])} eligible nonmisses | {"pass" if d["complete_cycle_wait"]["pass"] else "fail"} |',
              "", "## Failures and unestablished cohorts", "",
              "All excluded allocation IDs and exception observations are retained in guard_analysis.json. These are unavailable measurements, "
              "not passes. The table below separates guard rejection from a score that the guard admitted but the fixed decision could not accept.", "",
              "| Case | Guard-ineligible allocations | Admitted null allowance misses | Admitted wrong/overlap classification |", "|---|---|---|---|"]
    for case, row in result["cases"].items():
        mode = case.split("/")[1]
        null_misses = row["eligible_null_allowance_misses"] if mode in ("same", "reference_wait_once") else []
        bad = row["eligible_nonpass_allocations"] if mode in ("same", "reference_wait_once") else row["eligible_nonmiss_allocations"] if mode in ("work50", "wait_each", "wait_cycle") else []
        if row["ineligible_allocations"] or null_misses or bad:
            ids = lambda xs: ", ".join(map(str, xs)) if xs else "none"
            lines.append(f'| {case} | {ids(row["ineligible_allocations"])} | {ids(null_misses)} | {ids(bad)} |')
    elapsed = result["harness_elapsed_seconds"]
    lines += ["", "## Scope and reproduction", "",
              f'Harness median {elapsed["median"]:.2f}s per allocation, range {elapsed["minimum"]:.2f}–{elapsed["maximum"]:.2f}s, excluding Actions setup/upload. '
              "The operation cases are unchanged from v2, including all startup, commits, output checking and injected waits described there.", ""]
    lines += ["- " + item for item in result["interpretation"]]
    lines += ["", "Run `python experiments/64/v3/analyze_guard.py` to reproduce the result. "
              "The analyzer reuses v2's exact-source/fixture/runtime/completeness checks and does not refit. "
              "The reference configuration can be reproduced from the retained v2 data with `build_guard_config.py`; it must not be rebuilt from v3 observations. "
              "This is an experiment, not adoption of #64 or Riverhog/Fishhat qualification.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE / "observations.json")
    parser.add_argument("--config", type=Path, default=HERE / "guard_config.json")
    parser.add_argument("--output", type=Path, default=HERE / "guard_analysis.json")
    parser.add_argument("--report", type=Path, default=HERE / "GUARD_RESULTS.md")
    args = parser.parse_args()
    result = analyze(json.loads(args.source.read_text()), json.loads(args.config.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.report.write_text(render(result))
    print(json.dumps({"run_id": result["run_id"], "primary_family_pass_count": result["primary_family_pass_count"],
                      "all_adversarial_diagnostics_pass": result["all_adversarial_diagnostics_pass"]}))


if __name__ == "__main__":
    main()
