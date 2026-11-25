# #64 hosted-runner calibration — completed finite pilot

[Original Actions run](https://github.com/nashspence/all/actions/runs/45675949036) at `6d72d6ceea9ef02c40d56b8202f9df5be1643405`; 24/24 successful first-attempt jobs, 24 distinct runner IDs, 648 verified timing observations (24 allocations × 9 cases × 3 repetitions). Product source frozen at `03de186a044c9c6b365347485a6c4093ce831c79`. Every original job and record was matched to the run/commit/fixture identity; all 24 original artifact names/digests were retained in observations.json. The retained observations were extracted from original job logs, not from independent ZIP downloads. No discarded sample, no reruns of successful work.

## Predeclared decision, not adoption

First 12 allocation IDs establish median reference of their three-run means; maximum relative training deviation plus five percentage points gives candidate allowance; maximum acceptable 20%. Holdout allocation IDs 13–24 must all fall within that allowance. All 24 observations are retained. This is a finite empirical screen, not a confidence interval or an assertion of future coverage. All times in ms per complete declared observation (512 checks for each policy case, not a single 16-member batch). "yes" means supported by this specific finite pilot, not authority to enforce a product budget.

| Case | All allocation means (ms) | Training reference (ms) | Train max error | Candidate e | Holdout max error | Holdout outside | Supports ≤20% |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| cpu_p1 | 140.65–254.14 | 176.43 | 39.7% | 44.7% | 44.0% | 0/12 | no |
| cpu_p2 | 89.46–249.90 | 106.40 | 34.3% | 39.3% | 134.9% | 1/12 | no |
| cpu_p4 | 74.65–148.28 | 85.12 | 43.2% | 48.2% | 74.2% | 2/12 | no |
| files_warm | 32.01–77.38 | 33.19 | 92.9% | 97.9% | 133.2% | 1/12 | no |
| policy_p1 | 199.38–399.08 | 242.00 | 30.1% | 35.1% | 64.9% | 1/12 | no |
| policy_p2 | 148.13–278.36 | 165.41 | 33.7% | 38.7% | 68.3% | 3/12 | no |
| policy_p4 | 122.65–285.69 | 148.26 | 92.7% | 97.7% | 86.8% | 0/12 | no |
| sha256 | 128.46–182.44 | 143.78 | 25.0% | 30.0% | 26.9% | 0/12 | no |
| sqlite_full | 31.84–1342.13 | 34.62 | 2859.5% | 2864.5% | 3776.8% | 2/12 | no |

One candidate allowance covering all classes would be 2864.5%; the predeclared universal 20% screen does not pass. Do not infer a global multiplier from these observations. No product budget was adopted or changed. The same nominal four-vCPU label admits distinct CPU models; resource evidence includes four logical and affinity CPUs but not a usable cgroup-v2 quota value on all runners. Storage control uses SQLite's FULL commit API, not verified physical sync or power-loss guarantees.

## Paired scaling (same worker)

| Case | Two workers median speedup (range) | Four workers median speedup (range) |
|---|---:|---:|
| cpu | 1.62x (1.00–1.76x) | 2.03x (1.53–2.14x) |
| policy | 1.39x (1.29–1.60x) | 1.60x (1.10–1.70x) |

The policy case measures the real local repository-policy check in a disposable fixture. The 2/4 process-pool wrapper is experimental, not a supported product mode. Fixture construction and independent checking are outside the product timer; pool startup/shutdown and check file access are inside. No real network-backed owner audit, Riverhog or Fishhat operation has been qualified.

See observations.json, analysis.json, and analyze.mjs for original data, detailed summaries (including within-cohort spreads, CPU strata and environment), and an optional reproduction command: `node experiments/64/analyze.mjs`. The original README specifies the workload and analysis before execution. The first three launch attempts failed during workflow parsing (unquoted pip option containing colon-space); no jobs or observations were allocated in those attempts. Corrected source used a YAML folded scalar and full checkout for frozen-source verification. Original test workflow restored. The successful workflow is restricted to this experiment branch and the experiment script/workflow paths; results-only publication does not trigger it.
