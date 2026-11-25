#!/usr/bin/env python3
"""Freeze the v3 guard configuration from the already completed v2 campaign."""
import hashlib
import json
from pathlib import Path
import statistics

FIT_RUN = 45680767861
FIT_SOURCE = "7355aed8042e61eedc491428a063080a7f557f5b"
PRIMARY = ["policy16_p1", "policy512_p1", "policy512_p2", "policy512_p4", "files4096"]
FAMILIES = [f"policy{n}_p{p}" for n in (16, 512) for p in (1, 2, 4)] + ["files4096", "sqlite64", "cycle48", "cold16"]


def audit_case(family):
    return family + ("/wait_cycle" if family == "cycle48" else "/wait_each" if family == "cold16" else "/work50")


def main():
    here = Path(__file__).resolve().parent
    path = here.parent / "v2/observations.json"
    raw = path.read_bytes()
    source = json.loads(raw)
    assert source["run_id"] == FIT_RUN and source["source"] == FIT_SOURCE
    records = sorted(source["records"], key=lambda r: r["allocation"])
    assert [r["allocation"] for r in records] == list(range(1, 25))
    families = {}
    for family in FAMILIES:
        scores, guards, anchors = [], [], []
        for record in records:
            minimum = lambda case, role: min(sample["wall_ns"] for sample in record["samples"][case][role])
            ref = minimum(family + "/same", "reference")
            audit = minimum(audit_case(family), "reference")
            denominator = min(ref, audit)
            scores.append(minimum(family + "/same", "candidate") / denominator)
            guards.append(max(ref, audit) / denominator - 1)
            anchors.append(denominator / 1e6)
        maximum = max(abs(score - 1) for score in scores)
        error = maximum + 0.03
        families[family] = {
            "primary": family in PRIMARY, "same_case_audit": audit_case(family),
            "fit_max_null_error_all_24": maximum, "allowance": error,
            "allowance_within_cap": error <= 0.20,
            "reference_anchor_ms": statistics.median(anchors),
            "fit_guard_eligible_count": sum(g <= 0.10 for g in guards),
            "fit_null_budget_pass_count": sum(s / (1 - error) <= 1.20 for s in scores) if error < 1 else 0,
        }
    result = {
        "format": "all-reference-guard-config/v3", "status": "frozen_before_fresh_v3_validation",
        "fitted_from": {"run_id": FIT_RUN, "source": FIT_SOURCE, "sha256": hashlib.sha256(raw).hexdigest(),
                        "path": "experiments/64/v2/observations.json", "allocations": list(range(1, 25))},
        "primary_families": PRIMARY, "estimator": "ratio_of_minima_using_faster_reference",
        "guard_maximum_symmetric_relative_difference": 0.10,
        "guard_formula": "max(min(Rcase),min(Raudit))/min(min(Rcase),min(Raudit))-1",
        "score_formula": "min(Ccase)/min(min(Rcase),min(Raudit))",
        "maximum_allowance": 0.20, "fit_headroom": 0.03, "illustrative_budget_ratio": 1.20,
        "fresh_allocation_count": 24, "minimum_guard_eligible_per_cohort": 23,
        "fit_drops_or_recenterings": 0, "families": families,
        "interpretation": [
            "All 24 old campaign allocations fit the new rule; none remains a holdout for it.",
            "Every new campaign allocation validates the fixed rule; legacy fit/holdout record labels do not change this.",
            "The allowance is not clamped to 20%; values above the cap fail qualification.",
            "Only the five declared primary families support the primary success decision; all other cases remain visible.",
            "Guard failure means unestablished measurement, not candidate conformance or a discarded worker.",
            "A current candidate being slow cannot invalidate its reference guard.",
        ],
    }
    (here / "guard_config.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"fit_run_id": FIT_RUN, "primary": {f: families[f]["allowance"] for f in PRIMARY}}))


if __name__ == "__main__":
    main()
