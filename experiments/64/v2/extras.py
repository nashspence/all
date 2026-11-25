#!/usr/bin/env python3
"""Post-hoc cost and denominator diagnostics; not a new qualification screen."""
import json
from pathlib import Path
import statistics


def stats(xs):
    return {"minimum": min(xs), "median": statistics.median(xs), "maximum": max(xs)}


def main():
    here = Path(__file__).resolve().parent
    source = json.loads((here / "observations.json").read_text())
    records = sorted(source["records"], key=lambda r: r["allocation"])
    assert [r["allocation"] for r in records] == list(range(1, 25))
    assert len({r["runner_id"] for r in records}) == 24
    assert len({r["job_id"] for r in records}) == 24
    artifacts = source["artifacts"]
    assert {a["name"] for a in artifacts} == {f"paired-{i}" for i in range(1, 25)}
    assert all(a["workflow_run"]["id"] == source["run_id"] and
               a["workflow_run"]["head_sha"] == source["source"] for a in artifacts)
    families = [case.split("/")[0] for case in records[0]["samples"] if case.endswith("/same")]
    costs, guards = {}, {}
    for family in families:
        cost, product = [], []
        for r in records:
            sides = r["samples"][family + "/same"]
            cost.append(sum(s["wall_ns"] for values in sides.values() for s in values) / 1e6)
            product.append(sum(s["wall_ns"] for s in sides["candidate"]) / 1e6)
        costs[family] = {"six_executions_timed_ms": stats(cost), "three_candidate_executions_timed_ms": stats(product)}
        for case in records[0]["samples"]:
            if not case.startswith(family + "/") or case.endswith("/same"):
                continue
            rows = []
            for r in records:
                minimum = lambda c: min(s["wall_ns"] for s in r["samples"][c]["reference"])
                ratio = minimum(case) / minimum(family + "/same")
                rows.append({"allocation": r["allocation"], "reference_to_sentinel_ratio": ratio,
                             "outside_illustrative_20_percent": abs(ratio - 1) > 0.20})
            guards[case] = {"ratios": stats([x["reference_to_sentinel_ratio"] for x in rows]),
                           "outside_illustrative_20_percent": [x["allocation"] for x in rows if x["outside_illustrative_20_percent"]],
                           "observations": rows}
    result = {"status": "post_hoc_diagnostic_not_fresh_qualification", "source": source["source"],
              "run_id": source["run_id"], "artifact_metadata_count_verified": 24,
              "costs": costs, "denominator_guard_hypothesis": guards}
    (here / "extra_analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# Additional diagnostics after the predeclared v2 analysis", "",
             "**Post-hoc exploration, not a new qualified rule.** Every worker remains in these tables. "
             "The original estimator, allowance and acceptance conclusions are unchanged.", "",
             "## Incremental timed cost", "",
             "One ordinary calibration cohort contains three complete reference and three complete candidate executions. "
             "This measures the entire cohort's elapsed work, not the retained minimum. Setup, verification, Actions checkout and upload are outside these totals.", "",
             "| Family | Median six-execution total ms | Range ms | Median three-candidate total ms |", "|---|---:|---:|---:|"]
    for family, item in costs.items():
        c, p = item["six_executions_timed_ms"], item["three_candidate_executions_timed_ms"]
        lines.append(f'| {family} | {c["median"]:.2f} | {c["minimum"]:.2f}–{c["maximum"]:.2f} | {p["median"]:.2f} |')
    lines += ["", "## A denominator guard hypothesis", "",
              "Compare a case's minimum reference time to that family's separately executed unchanged-reference minimum on the same worker. "
              "This treats the unchanged execution as a possible sentinel. The illustrative ±20% threshold was examined after the run; "
              "it was not part of acceptance, and its exclusions cannot repair the published calibration result.", "",
              "| Case | Reference/sentinel ratio range | Median | Outside illustrative ±20% /24 |", "|---|---:|---:|---:|"]
    for case, item in guards.items():
        s = item["ratios"]
        lines.append(f'| {case} | {s["minimum"]:.3f}–{s["maximum"]:.3f} | {s["median"]:.3f} | {len(item["outside_illustrative_20_percent"])}/24 |')
    lines += ["", "The persistent reference-only delay is visible against the independent execution. "
              "A single slow reference is already resisted by the ratio of minima. The same candidate guard flags some genuine unmodified "
              "small-pool and SQLite observations, so the availability consequence must be reported rather than hidden. "
              "This guard cannot detect contamination shared by both reference and sentinel; immutable source/dependency artifacts and "
              "a genuinely independent reference remain necessary.", "",
              "## Scope of evidence and next experiment", "",
              "The fresh v2 screen supports a practical candidate mechanism for serial processing, larger parallel processing windows "
              "and warm file work. No additional general sweep is needed to state that finite result. "
              "Calling it a universal durability or tiny parallel-operation gate would require new evidence. "
              "A targeted follow-up can retain the complete operation but time a fixed window of several independent complete operations, "
              "including every pool startup and database create/commit/close. Predeclare any reference-stability guard, report every "
              "rejected allocation, and require unchanged and added-work cases to pass a fresh holdout. "
              "The window is its own timing contract and cannot establish individual-operation tail latency. "
              "Do not merely add more retries until a favorable result appears.", "",
              "An enforcement rollout also needs confirmation across later allocations/image changes and near-boundary changes smaller "
              "than the deliberately large +50% work dose. The present run is not a long-term false-alarm estimate.", "",
              "Reproduce with `python experiments/64/v2/extras.py`. Artifact names, source SHA and run IDs match the retained metadata "
              "for all 24 artifacts. Observations came from job-log JSON; the ZIP payloads were not independently downloaded.", ""]
    (here / "EXTRA.md").write_text("\n".join(lines))
    print(json.dumps({"status": result["status"], "artifact_metadata_count_verified": 24,
                      "cost_families": len(costs), "guard_diagnostics": len(guards)}))


if __name__ == "__main__":
    main()
