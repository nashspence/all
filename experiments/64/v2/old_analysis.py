#!/usr/bin/env python3
"""Exploratory reanalysis of the first #64 pilot; no fresh qualification."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


ESTIMATORS = {
    "first": lambda values: values[0],
    "mean": statistics.mean,
    "median": statistics.median,
    "minimum": min,
}
MATCHES = [
    ("policy_p1", "cpu_p1"),
    ("policy_p2", "cpu_p2"),
    ("policy_p4", "cpu_p4"),
    ("policy_p1", "sha256"),
    ("policy_p1", "files_warm"),
    ("sqlite_full", "cpu_p1"),
    ("sqlite_full", "files_warm"),
]


def screen(records, values):
    training = [value for record, value in zip(records, values) if record["allocation"] <= 12]
    holdout = [value for record, value in zip(records, values) if record["allocation"] > 12]
    reference = statistics.median(training)
    training_errors = [abs(value / reference - 1) for value in training]
    holdout_errors = [abs(value / reference - 1) for value in holdout]
    allowance = max(training_errors) + 0.05
    return {
        "training_reference": reference,
        "train_max_relative_error": max(training_errors),
        "candidate_allowance": allowance,
        "heldout_max_relative_error": max(holdout_errors),
        "heldout_outside_candidate_allowance": sum(error > allowance for error in holdout_errors),
        "within_original_20_percent_screen": allowance <= 0.20 and all(error <= allowance for error in holdout_errors),
        "all_allocation_min": min(values),
        "all_allocation_max": max(values),
        "all_allocation_max_min_ratio": max(values) / min(values),
        "values_in_allocation_order": values,
    }


def analyse(source):
    records = sorted(source["records"], key=lambda record: record["allocation"])
    assert [record["allocation"] for record in records] == list(range(1, 25))
    assert all(record["verified"] and len(record["samples_ns"]) == 9 for record in records)
    assert all(len(times) == 3 and all(time > 0 for time in times)
               for record in records for times in record["samples_ns"].values())
    raw = []
    normalized = []
    ratios = []
    for case in sorted(records[0]["samples_ns"]):
        for name, estimator in ESTIMATORS.items():
            values = [estimator(record["samples_ns"][case]) / 1e6 for record in records]
            raw.append({"case": case, "estimator": name, "unit": "milliseconds", **screen(records, values)})
    for target, control in MATCHES:
        for name, estimator in ESTIMATORS.items():
            values = [estimator(record["samples_ns"][target]) / estimator(record["samples_ns"][control])
                      for record in records]
            normalized.append({"target": target, "control": control, "estimator": name,
                               "method": "ratio_of_estimates", "unit": "ratio", **screen(records, values)})
        # The original cases were rotated within each repetition; same-index
        # samples are not temporally adjacent reference/candidate pairs.
        values = [min(target_ns / control_ns for target_ns, control_ns in
                      zip(record["samples_ns"][target], record["samples_ns"][control]))
                  for record in records]
        differences = []
        for record, value in zip(records, values):
            ratio_of_minima = min(record["samples_ns"][target]) / min(record["samples_ns"][control])
            target_index, control_index = min(
                enumerate(record["samples_ns"][target]), key=lambda pair: pair[1])[0], min(
                enumerate(record["samples_ns"][control]), key=lambda pair: pair[1])[0]
            selected_index = min(range(3), key=lambda i: record["samples_ns"][target][i] /
                                 record["samples_ns"][control][i])
            differences.append({
                "allocation": record["allocation"],
                "ratio_of_minima": ratio_of_minima,
                "minimum_of_same_index_ratios": value,
                "relative_difference_from_ratio_of_minima": value / ratio_of_minima - 1,
                "target_minimum_repeat_index": target_index,
                "control_minimum_repeat_index": control_index,
                "selected_same_index_ratio_repeat_index": selected_index,
                "selected_control_over_minimum": record["samples_ns"][control][selected_index] /
                                                  min(record["samples_ns"][control]),
            })
        ratios.append({"target": target, "control": control,
                       "method": "minimum_of_same_index_ratios_NOT_close_pairs", "unit": "ratio",
                       **screen(records, values), "comparison": differences})
    return {
        "format": "all-calibration-estimator-exploration/v2",
        "source_run_id": source["run_id"],
        "source_commit": source["source"],
        "frozen_product_commit": source["frozen_source"],
        "allocation_order": [record["allocation"] for record in records],
        "status": "exploratory_old_data_not_fresh_validation",
        "interpretation": [
            "Original IDs 1-12 and 13-24 are retained for comparability, not a new independent holdout.",
            "Each case has three full verified executions; the physical minimum is one actual completion time.",
            "Ratios of minima can combine target and control minima from different repetitions.",
            "Minimum of same-index ratios can look fast because its control is slow; these original observations were not close temporal pairs.",
            "Selecting the minimum changes the estimand to observed best completion and does not establish typical or tail latency.",
            "No sample is removed from the retained source or any calculation definition.",
            "The 20% cap and five percentage-point headroom are original exploratory screen values, not adopted policy.",
        ],
        "raw": raw,
        "normalized": normalized,
        "minimum_of_same_index_ratios": ratios,
    }


def notes(result):
    lines = [
        "# Reanalysis: first, mean, median and minimum of three",
        "",
        "**Exploratory reuse of the original 24-worker dataset; not fresh validation.** "
        "Original fit IDs 1–12 and holdout IDs 13–24 are preserved only to make comparisons exact. "
        "The previous holdout has already been examined. No calibrated enforcement rule is established here.",
        "",
        "Run: https://github.com/nashspence/all/actions/runs/45675949036. "
        "Source data are the sibling `../observations.json`. Reproduce with `python experiments/64/v2/old_analysis.py`.",
        "",
        "## Raw timing",
        "",
        "Values below are maximum relative deviation from the median of training allocation estimates. "
        "Each original policy observation includes 512 complete local policy checks, not one cold 16-member operation.",
        "",
        "| Case | Estimator | Train max error | Original holdout max error | Candidate e | Meets original screen |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in result["raw"]:
        lines.append(f'| {row["case"]} | {row["estimator"]} | {row["train_max_relative_error"]:.1%} | '
                     f'{row["heldout_max_relative_error"]:.1%} | {row["candidate_allowance"]:.1%} | '
                     f'{"yes" if row["within_original_20_percent_screen"] else "no"} |')
    lines += ["", "## Normalized same-allocation ratios", "",
              "`estimate(target) / estimate(control)` using the same estimator on both sides. "
              "The control is generic, not a frozen copy of the production operation. CPU and storage response need not match.", "",
              "| Target/control | Estimator | Train max error | Original holdout max error | Candidate e | Meets original screen |",
              "|---|---|---:|---:|---:|---|"]
    for row in result["normalized"]:
        lines.append(f'| {row["target"]}/{row["control"]} | {row["estimator"]} | {row["train_max_relative_error"]:.1%} | '
                     f'{row["heldout_max_relative_error"]:.1%} | {row["candidate_allowance"]:.1%} | '
                     f'{"yes" if row["within_original_20_percent_screen"] else "no"} |')
    lines += ["", "## Selection and interpretation", "",
              "The physical minimum is one actual full correct completion on that worker. "
              "The ratio of minima need not describe one temporal pair. Taking the minimum of three ratios "
              "can instead reward an unusually slow denominator. The JSON retains each allocation's selected "
              "indices and denominator inflation to make that distinction visible. These original same-index "
              "observations were rotated among nine cases and are not close reference/candidate pairs.", "",
              "A low minimum cannot establish typical latency, tail latency, or absence of intermittent product "
              "stalling. It can support a best-completion estimator under explicitly repeatable reset/cache "
              "semantics, subject to fresh validation. It does not remove permanent CPU/storage differences.", "",
              "Neither arithmetic averaging nor minimum selection can turn a resource-mismatched CPU control "
              "into a storage calibration. An apparent successful row is a hypothesis for a fresh, predeclared "
              "experiment; selecting it after reading this table would reuse the original holdout.", ""]
    return "\n".join(lines)


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=here.parent / "observations.json")
    parser.add_argument("--output", type=Path, default=here / "old_analysis.json")
    parser.add_argument("--notes", type=Path, default=here / "old_analysis.md")
    args = parser.parse_args()
    result = analyse(json.loads(args.source.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.notes.write_text(notes(result))
    print(json.dumps({"raw_cases": len(result["raw"]), "normalized_cases": len(result["normalized"]),
                      "output": str(args.output), "notes": str(args.notes)}))


if __name__ == "__main__":
    main()
