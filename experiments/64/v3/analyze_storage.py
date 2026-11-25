"""Reproduce the predeclared v3 storage screens from twelve raw records."""
import argparse
import json
from pathlib import Path
import statistics as st


def require(ok, message):
    if not ok:
        raise ValueError(message)


def scores(records, extent, mode, statistic=min):
    result = []
    for record in records:
        case = record["samples"][f"sqlite{extent}/{mode}"]
        a, b, c = [statistic(x["wall_ns"] for x in case[role]) for role in ("reference", "guard", "candidate")]
        result.append({"allocation": record["allocation"], "ratio": c / min(a, b),
                       "guard": max(a, b) / min(a, b) - 1, "eligible": max(a, b) / min(a, b) <= 1.10})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("observations", nargs="?", default=str(Path(__file__).with_name("storage_observations.json")))
    args = parser.parse_args()
    records = json.loads(Path(args.observations).read_text())
    require(isinstance(records, list), "expected an array of raw records")
    records.sort(key=lambda x: x["allocation"])
    require([x["allocation"] for x in records] == list(range(1, 13)), "twelve unique allocations required")
    require(len({x["source"] for x in records}) == 1, "mixed source")
    require(len({x["script_sha256"] for x in records}) == 1 and len({x["fixture_sha256"] for x in records}) == 1, "mixed script/fixtures")
    for record in records:
        require(record["format"] == "all-storage-calibration/v3" and not record["smoke"], "invalid provenance")
        require(record["phase"] == ("fit" if record["allocation"] <= 6 else "holdout"), "phase mismatch")
        require(record["complete"], f"incomplete allocation {record['allocation']}; report separately, never qualify")
        require(record["environment"]["python"] == "3.11.9", "runtime mismatch")
        require(record["environment"]["logical_cpus"] == record["environment"]["affinity_count"] == 4, "CPU allocation")
        require(len(record["execution_order"]) == 54, "execution count")
        for extent in (64, 256, 1024):
            for mode in ("same", "work50"):
                case = record["samples"][f"sqlite{extent}/{mode}"]
                for role in ("reference", "guard", "candidate"):
                    require(len(case[role]) == 3, "sample count")
                    for sample in case[role]:
                        expected = extent + (extent // 2 if mode == "work50" and role == "candidate" else 0)
                        require(sample["verified"] and sample["error"] is None and sample["wall_ns"] > 0, "invalid sample")
                        require(sample["data_commits"] == expected and sample["schema_commits"] == 1, "commit mismatch")
    report = {"source": records[0]["source"], "allocations": 12, "timings": 648, "families": {}}
    lines = ["# v3 complete SQLite window results", "", "Twelve allocations; first six fit, last six held out by preassigned ID. This is a finite exploratory screen, not physical durability qualification or policy adoption.", "", "Primary score: minimum candidate / minimum of both reference cohorts. The 10% reference agreement guard uses no candidate timing. Fit e includes every fit allocation, even a guard rejection. No observations are discarded.", "", "| Data commits | Fit e | Eligible null /6 | Eligible work /6 | Null within e | Null budget pass | Work >1.20 | Work budget miss | Strong screen |", "|---|---:|---:|---:|---|---:|---:|---:|---|"]
    for extent in (64, 256, 1024):
        same, work = scores(records, extent, "same"), scores(records, extent, "work50")
        e = max(abs(x["ratio"] - 1) for x in same[:6]) + 0.03
        null = [x for x in same[6:] if x["eligible"]]
        dose = [x for x in work[6:] if x["eligible"]]
        within = e <= 0.20 and all(abs(x["ratio"] - 1) <= e for x in null)
        good = sum(e <= 0.20 and x["ratio"] / (1 - e) <= 1.20 for x in null)
        sensitive = sum(x["ratio"] > 1.20 for x in dose)
        misses = sum(e <= 0.20 and x["ratio"] / (1 + e) > 1.20 for x in dose)
        strong = within and len(null) >= 5 and len(dose) >= 5 and good == len(null) and misses == len(dose)
        detail = {"e": e, "same": same, "work50": work, "eligible_null": len(null), "eligible_work": len(dose), "null_screen": within, "null_budget_pass": good, "work_sensitivity": sensitive, "work_budget_miss": misses, "strong_screen": strong, "diagnostics": {}}
        for name, statistic in (("first", lambda xs: list(xs)[0]), ("mean", st.mean), ("median", st.median)):
            detail["diagnostics"][name] = {"same": scores(records, extent, "same", statistic), "work50": scores(records, extent, "work50", statistic)}
        report["families"][str(extent)] = detail
        lines.append(f"| {extent} | {e:.1%} | {len(null)} | {len(dose)} | {'yes' if within else 'no'} | {good} | {sensitive} | {misses} | {'pass' if strong else 'unestablished'} |")
    elapsed = [x["elapsed_ns"] / 1e9 for x in records]
    report["elapsed_seconds"] = {"min": min(elapsed), "median": st.median(elapsed), "max": max(elapsed)}
    lines += ["", f"Harness elapsed: median {st.median(elapsed):.2f}s, range {min(elapsed):.2f}–{max(elapsed):.2f}s. Each complete observation includes schema creation, every individual commit and connection close; row/integrity verification follows the timer.", "", "## Guard rejections", ""]
    for extent, detail in report["families"].items():
        for mode in ("same", "work50"):
            rejected = [x["allocation"] for x in detail[mode] if not x["eligible"]]
            lines.append(f"- sqlite{extent}/{mode}: {rejected or 'none'}")
    lines += ["", "A longer qualified window does not establish tiny-operation latency. Persistently contaminated references may still agree. All raw times and first/mean/median diagnostic scores remain available; these diagnostics are not promoted winners on the same holdout.", ""]
    destination = Path(__file__).parent
    (destination / "storage_analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    (destination / "STORAGE_RESULTS.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
