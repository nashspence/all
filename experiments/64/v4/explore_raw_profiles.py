"""Exploratory raw-time summaries only; no normalization or policy adoption."""
from collections import defaultdict
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
ESTIMATORS = {
    "first": lambda xs: xs[0],
    "minimum": min,
    "mean": statistics.mean,
    "maximum": max,
}
GENERIC_PROBES = ("cpu_p1", "cpu_p2", "cpu_p4", "sha256", "files_warm", "sqlite_full")
# Exploratory envelopes chosen before a future fresh campaign. No tested product
# runtime enters a probe score and no product time or budget is multiplied.
ILLUSTRATIVE_PROBE_CAPS_MS = {
    "cpu_p1": 300, "cpu_p2": 250, "cpu_p4": 175,
    "sha256": 225, "files_warm": 100,
}
PRODUCT_CASES = (
    "policy16_p1/same", "policy16_p2/same", "policy16_p4/same",
    "cycle48/same", "cycle48/wait_cycle", "cold16/same",
    "files4096/same", "sqlite64/same",
)


def summary(values):
    return {"minimum_ms": min(values), "median_ms": statistics.median(values), "maximum_ms": max(values)}


def main():
    old = json.loads((ROOT / "observations.json").read_text())["records"]
    result = {
        "status": "exploratory reuse of earlier data, not fresh validation or authority",
        "source_runs": [45675949036, 45680767861, 45682545450],
        "no_normalization": True,
        "generic_controls": {}, "old_hardware_strata": {},
        "product_raw_cases": {}, "illustrative_probe_caps_ms": ILLUSTRATIVE_PROBE_CAPS_MS,
        "illustrative_probe_eligibility": {},
    }
    for case in GENERIC_PROBES:
        result["generic_controls"][case] = {
            name: summary([fn(r["samples_ns"][case]) / 1e6 for r in old])
            for name, fn in ESTIMATORS.items()
        }
    by_model = defaultdict(list)
    for record in old:
        by_model[record["cpu_model"]].append(record)
    for model, rows in by_model.items():
        result["old_hardware_strata"][model] = {
            "allocations": [r["allocation"] for r in rows],
            "probe_minimum_ranges_ms": {
                case: summary([min(r["samples_ns"][case]) / 1e6 for r in rows])
                for case in GENERIC_PROBES
            },
        }
    for name, fn in ESTIMATORS.items():
        admitted = [r["allocation"] for r in old if all(
            fn(r["samples_ns"][case]) / 1e6 <= cap for case, cap in ILLUSTRATIVE_PROBE_CAPS_MS.items()
        )]
        result["illustrative_probe_eligibility"][name] = {
            "eligible": admitted, "rejected": [r["allocation"] for r in old if r["allocation"] not in admitted],
            "eligible_count": len(admitted), "total_count": len(old),
        }
    result["storage_envelope_diagnostic"] = {
        str(cap): {name: sum(fn(r["samples_ns"]["sqlite_full"]) / 1e6 <= cap for r in old)
                   for name, fn in ESTIMATORS.items()}
        for cap in (100, 125, 250, 500, 1000, 2000, 4000)
    }
    combined = []
    for relative in ("v2/observations.json", "v3/observations.json"):
        combined += json.loads((ROOT / relative).read_text())["records"]
    for case in PRODUCT_CASES:
        values = [[s["wall_ns"] / 1e6 for s in r["samples"][case]["candidate"]] for r in combined]
        result["product_raw_cases"][case] = {
            name: summary([fn(xs) for xs in values]) for name, fn in ESTIMATORS.items()
        }
        result["product_raw_cases"][case]["allocation_count"] = len(values)
    result["limitations"] = [
        "All envelope choices are exploratory; they require a new predeclared validation.",
        "Probe caps do not become product budgets and do not establish operator usability.",
        "Historical controls were not before/after bookends of every product case.",
        "No inference that processor identity alone determines storage latency.",
        "A minimum is an achieved complete execution, not maximum or typical operator latency.",
        "There is no distinct retained memory-bandwidth control in the original pilot.",
        "SQL FULL API behavior does not qualify physical persistence or power-loss safety.",
    ]
    out = Path(__file__).with_name("raw_profile_exploration.json")
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
