# Additional diagnostics after the predeclared v2 analysis

**Post-hoc exploration, not a new qualified rule.** Every worker remains in these tables. The original estimator, allowance and acceptance conclusions are unchanged.

## Incremental timed cost

One ordinary calibration cohort contains three complete reference and three complete candidate executions. This measures the entire cohort's elapsed work, not the retained minimum. Setup, verification, Actions checkout and upload are outside these totals.

| Family | Median six-execution total ms | Range ms | Median three-candidate total ms |
|---|---:|---:|---:|
| cold16 | 373.27 | 323.66–536.40 | 187.33 |
| cycle48 | 137.95 | 113.00–224.04 | 69.33 |
| files4096 | 302.19 | 193.20–499.66 | 151.94 |
| policy16_p1 | 48.17 | 38.88–75.69 | 24.53 |
| policy16_p2 | 84.71 | 63.86–313.12 | 46.92 |
| policy16_p4 | 83.81 | 59.38–162.10 | 40.64 |
| policy512_p1 | 1443.72 | 1196.50–2360.64 | 723.53 |
| policy512_p2 | 1063.79 | 886.90–1736.13 | 530.63 |
| policy512_p4 | 890.19 | 744.56–1432.54 | 446.33 |
| sqlite64 | 393.52 | 180.76–3721.83 | 194.30 |

## A denominator guard hypothesis

Compare a case's minimum reference time to that family's separately executed unchanged-reference minimum on the same worker. This treats the unchanged execution as a possible sentinel. The illustrative ±20% threshold was examined after the run; it was not part of acceptance, and its exclusions cannot repair the published calibration result.

| Case | Reference/sentinel ratio range | Median | Outside illustrative ±20% /24 |
|---|---:|---:|---:|
| cold16/wait_each | 0.977–1.021 | 1.001 | 0/24 |
| cycle48/wait_cycle | 0.973–1.017 | 0.998 | 0/24 |
| files4096/work50 | 0.986–1.039 | 1.001 | 0/24 |
| policy16_p1/reference_wait_each | 6.172–11.104 | 9.340 | 24/24 |
| policy16_p1/reference_wait_once | 0.990–1.052 | 1.027 | 0/24 |
| policy16_p1/wait_each | 0.959–1.053 | 0.987 | 0/24 |
| policy16_p1/wait_once | 0.945–1.016 | 0.988 | 0/24 |
| policy16_p1/work50 | 0.956–1.020 | 0.984 | 0/24 |
| policy16_p2/work50 | 0.789–1.249 | 0.985 | 3/24 |
| policy16_p4/work50 | 0.920–1.071 | 0.995 | 0/24 |
| policy512_p1/work50 | 0.989–1.008 | 0.998 | 0/24 |
| policy512_p2/work50 | 0.966–1.066 | 0.993 | 0/24 |
| policy512_p4/work50 | 0.947–1.028 | 0.995 | 0/24 |
| sqlite64/work50 | 0.726–1.649 | 0.981 | 6/24 |

The persistent reference-only delay is visible against the independent execution. A single slow reference is already resisted by the ratio of minima. The same candidate guard flags some genuine unmodified small-pool and SQLite observations, so the availability consequence must be reported rather than hidden. This guard cannot detect contamination shared by both reference and sentinel; immutable source/dependency artifacts and a genuinely independent reference remain necessary.

## Scope of evidence and next experiment

The fresh v2 screen supports a practical candidate mechanism for serial processing, larger parallel processing windows and warm file work. No additional general sweep is needed to state that finite result. Calling it a universal durability or tiny parallel-operation gate would require new evidence. A targeted follow-up can retain the complete operation but time a fixed window of several independent complete operations, including every pool startup and database create/commit/close. Predeclare any reference-stability guard, report every rejected allocation, and require unchanged and added-work cases to pass a fresh holdout. The window is its own timing contract and cannot establish individual-operation tail latency. Do not merely add more retries until a favorable result appears.

An enforcement rollout also needs confirmation across later allocations/image changes and near-boundary changes smaller than the deliberately large +50% work dose. The present run is not a long-term false-alarm estimate.

Reproduce with `python experiments/64/v2/extras.py`. Artifact names, source SHA and run IDs match the retained metadata for all 24 artifacts. Observations came from job-log JSON; the ZIP payloads were not independently downloaded.
