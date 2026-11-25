# #64 paired-reference calibration: v2 results

[Actions run](https://github.com/nashspence/all/actions/runs/45680767861) at `7355aed8042e61eedc491428a063080a7f557f5b`. 24 complete allocations, 24 case combinations, three adjacent reference/candidate pairs: **3,456 verified timings**. The primary estimator and thresholds were declared before collection in PLAN.md. This is a finite experiment, not policy adoption or Riverhog/Fishhat qualification.

## Primary: minimum candidate / minimum reference

Fit IDs 1–12 define e = maximum A/A deviation from 1 + 3 percentage points, capped at 20%. Every heldout A/A ratio (IDs 13–24) must remain inside that fixed allowance. Sensitivity independently requires every heldout +50%-work ratio >1.20. No timing was removed or recentered.

| Workload | Fit max A/A error | e | Holdout max A/A error | Null screen | +50% work >1.20 | Null budget pass | Work budget miss |
|---|---:|---:|---:|---|---:|---:|---:|
| policy16_p1 | 4.8% | 7.8% | 4.1% | pass | 12/12 | 12/12 | 12/12 |
| policy16_p2 | 19.3% | 22.3% | 26.7% | fail | 6/12 | 0/12 | 0/12 |
| policy16_p4 | 10.3% | 13.3% | 7.9% | pass | 6/12 | 12/12 | 0/12 |
| policy512_p1 | 0.6% | 3.6% | 1.1% | pass | 12/12 | 12/12 | 12/12 |
| policy512_p2 | 5.2% | 8.2% | 7.9% | pass | 12/12 | 12/12 | 12/12 |
| policy512_p4 | 3.0% | 6.0% | 3.4% | pass | 12/12 | 12/12 | 12/12 |
| files4096 | 1.9% | 4.9% | 1.5% | pass | 12/12 | 12/12 | 12/12 |
| sqlite64 | 50.1% | 53.1% | 20.6% | fail | 11/12 | 0/12 | 0/12 |
| cycle48 | 2.9% | 5.9% | 2.4% | pass | n/a | 12/12 | n/a |
| cold16 | 2.2% | 5.2% | 2.9% | pass | n/a | 12/12 | n/a |

The final two columns use qualified conservative bands against an illustrative budget of 1.20 reference units: upper=ratio/(1−e) must be ≤1.20 for pass; lower=ratio/(1+e) must exceed 1.20 for miss. A failed null calibration leaves qualification unestablished even if an arithmetic band looks favorable.

## Estimator diagnostics (same predeclared screen)

These are diagnostics. Selecting a different estimator after viewing these results requires new validation.

| Estimator | Families passing null screen /10 | Added-work families passing sensitivity /8 | Families passing both /8 | Stronger conservative screen /8 |
|---|---:|---:|---:|---:|
| minimum | 8/10 | 5/8 | 5/8 | 5/8 |
| first | 4/10 | 4/8 | 3/8 | 2/8 |
| mean | 6/10 | 5/8 | 4/8 | 3/8 |
| median | 6/10 | 5/8 | 4/8 | 4/8 |

## Raw and reference-equivalent timing

These reference anchors are the median of fit workers' minimum reference times, fixed for interpreting the holdout. They provide reference-equivalent units: anchor × candidate/reference. They are not fixed-hardware latency claims or authoritative budgets. All times below are milliseconds for the full named observation.

| Family | Experimental anchor ms | Raw null reference min–max ms | Raw null candidate min–max ms |
|---|---:|---:|---:|
| policy16_p1 | 7.875 | 6.324–12.372 | 6.430–12.576 |
| policy16_p2 | 12.866 | 8.545–20.154 | 8.259–19.863 |
| policy16_p4 | 14.882 | 9.611–19.519 | 9.298–20.547 |
| policy512_p1 | 249.015 | 197.478–384.546 | 197.075–386.149 |
| policy512_p2 | 180.901 | 135.570–269.860 | 131.185–278.775 |
| policy512_p4 | 160.682 | 119.962–235.151 | 121.250–235.175 |
| files4096 | 57.208 | 31.007–81.126 | 30.866–81.626 |
| sqlite64 | 49.181 | 22.148–91.128 | 24.873–105.587 |
| cycle48 | 23.488 | 18.537–37.021 | 18.490–36.833 |
| cold16 | 69.336 | 53.013–87.410 | 53.095–87.682 |

## Wait and denominator diagnostics

Each injection adds 64 ms of actual timed waiting. The one-off wait is the middle repeat; the full-cycle case includes one wait in every complete three-operation window. The ratio below is the median across all 24 allocation ratios. No added wait is subtracted.

| Case | Minimum ratio | Mean ratio | Median ratio | First ratio |
|---|---:|---:|---:|---:|
| policy16_p1/wait_each | 9.597 | 9.040 | 9.044 | 9.065 |
| policy16_p1/wait_once | 1.018 | 3.715 | 1.007 | 0.997 |
| policy16_p1/reference_wait_once | 0.973 | 0.271 | 0.972 | 0.977 |
| policy16_p1/reference_wait_each | 0.106 | 0.111 | 0.111 | 0.111 |
| cycle48/wait_cycle | 3.877 | 3.817 | 3.815 | 3.786 |
| cold16/wait_each | 2.043 | 2.022 | 2.015 | 1.995 |

| Denominator case | Ratio of minima median | Minimum of pair ratios median |
|---|---:|---:|
| policy16_p1/same | 1.023 | 1.004 |
| policy16_p1/reference_wait_once | 0.973 | 0.114 |
| policy16_p1/reference_wait_each | 0.106 | 0.106 |

A fast minimum cannot establish typical or tail latency. A minimum ratio can be falsely reduced by a slow reference; a persistently contaminated reference can also corrupt the ratio of minima. These controls diagnose the limitation rather than authorize discarding workers.

## Same-worker scaling

Experimental outer pool; no product parallelism claim. Startup and shutdown remain timed.

| Case/role | Median T1/Tp | Range |
|---|---:|---:|
| policy16_p2/reference | 0.641× | 0.516–0.901× |
| policy16_p2/candidate | 0.655× | 0.536–0.931× |
| policy16_p4/reference | 0.603× | 0.479–0.781× |
| policy16_p4/candidate | 0.596× | 0.488–0.836× |
| policy512_p2/reference | 1.433× | 1.346–1.653× |
| policy512_p2/candidate | 1.432× | 1.323–1.615× |
| policy512_p4/reference | 1.626× | 1.387–1.685× |
| policy512_p4/candidate | 1.622× | 1.378–1.698× |

## Environment and cost

24 allocations; verified unique runner IDs: 24. Harness elapsed per allocation: median 10.99s, range 10.40–17.79s. This excludes Actions checkout/setup/upload. Detailed elapsed and timed totals are retained in analysis.json.

| CPU model | Allocations |
|---|---|
| AMD EPYC 9V74 80-Core Processor | 1, 2, 4, 8, 11, 15, 18 |
| Intel(R) Xeon(R) 6975P-C | 3, 6, 10, 12, 14, 20, 21, 22, 23, 24 |
| AMD EPYC 7763 64-Core Processor | 5, 19 |
| Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz | 7 |
| AMD EPYC 9V45 96-Core Processor | 9, 13, 17 |
| INTEL(R) XEON(R) PLATINUM 8573C | 16 |

## Limits and reproduction

- Finite heldout screen, not a statistical confidence interval or long-term false-alarm estimate.
- Both waves occur in one short campaign; weekly image or future workload transfer is unqualified.
- Minimum is the primary estimator; other estimators are diagnostics, not post-hoc promoted winners.
- Experimental fit reference anchors and 1.20 budget ratio are not adopted operator usability targets.
- Process-pool parallelism and process-cold wrapper are experimental, not supported product modes.
- SQLite FULL API timings are not physical persistence or power-loss qualification.
- Reference and candidate share pinned runtime/dependency versions; upgrades require independently packaged reference dependencies.
- Reference/candidate mixtures can diverge; periodic product cost can vanish from minimum estimates.

Run `python experiments/64/v2/analyze.py` from the repository checkout. The script validates completeness, source and fixture identities, runtime, counts, correct-output flags, injected waits and adjacency before writing analysis.json and this report. The raw observations remain authoritative; workflow success only establishes successful measurement collection.
