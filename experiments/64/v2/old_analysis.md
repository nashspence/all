# Reanalysis: first, mean, median and minimum of three

**Exploratory reuse of the original 24-worker dataset; not fresh validation.** Original fit IDs 1–12 and holdout IDs 13–24 are preserved only to make comparisons exact. The previous holdout has already been examined. No calibrated enforcement rule is established here.

Run: https://github.com/nashspence/all/actions/runs/45675949036. Source data are the sibling `../observations.json`. Reproduce with `python experiments/64/v2/old_analysis.py`.

## Raw timing

Values below are maximum relative deviation from the median of training allocation estimates. Each original policy observation includes 512 complete local policy checks, not one cold 16-member operation.

| Case | Estimator | Train max error | Original holdout max error | Candidate e | Meets original screen |
|---|---|---:|---:|---:|---|
| cpu_p1 | first | 43.1% | 48.4% | 48.1% | no |
| cpu_p1 | mean | 39.7% | 44.0% | 44.7% | no |
| cpu_p1 | median | 38.2% | 44.4% | 43.2% | no |
| cpu_p1 | minimum | 38.3% | 39.9% | 43.3% | no |
| cpu_p2 | first | 33.0% | 305.2% | 38.0% | no |
| cpu_p2 | mean | 34.3% | 134.9% | 39.3% | no |
| cpu_p2 | median | 36.2% | 39.3% | 41.2% | no |
| cpu_p2 | minimum | 36.9% | 39.4% | 41.9% | no |
| cpu_p4 | first | 47.1% | 164.3% | 52.1% | no |
| cpu_p4 | mean | 43.2% | 74.2% | 48.2% | no |
| cpu_p4 | median | 42.0% | 60.0% | 47.0% | no |
| cpu_p4 | minimum | 41.8% | 59.8% | 46.8% | no |
| files_warm | first | 91.0% | 131.3% | 96.0% | no |
| files_warm | mean | 92.9% | 133.2% | 97.9% | no |
| files_warm | median | 91.1% | 130.4% | 96.1% | no |
| files_warm | minimum | 93.5% | 133.7% | 98.5% | no |
| policy_p1 | first | 32.9% | 66.6% | 37.9% | no |
| policy_p1 | mean | 30.1% | 64.9% | 35.1% | no |
| policy_p1 | median | 30.5% | 63.9% | 35.5% | no |
| policy_p1 | minimum | 27.7% | 65.2% | 32.7% | no |
| policy_p2 | first | 30.9% | 58.9% | 35.9% | no |
| policy_p2 | mean | 33.7% | 68.3% | 38.7% | no |
| policy_p2 | median | 32.5% | 64.1% | 37.5% | no |
| policy_p2 | minimum | 44.0% | 81.2% | 49.0% | no |
| policy_p4 | first | 156.0% | 68.3% | 161.0% | no |
| policy_p4 | mean | 92.7% | 86.8% | 97.7% | no |
| policy_p4 | median | 52.6% | 86.6% | 57.6% | no |
| policy_p4 | minimum | 48.3% | 58.9% | 53.3% | no |
| sha256 | first | 25.4% | 26.9% | 30.4% | no |
| sha256 | mean | 25.0% | 26.9% | 30.0% | no |
| sha256 | median | 25.1% | 27.1% | 30.1% | no |
| sha256 | minimum | 25.0% | 26.3% | 30.0% | no |
| sqlite_full | first | 7800.0% | 10416.2% | 7805.0% | no |
| sqlite_full | mean | 2859.5% | 3776.8% | 2864.5% | no |
| sqlite_full | median | 225.4% | 231.8% | 230.4% | no |
| sqlite_full | minimum | 184.7% | 196.5% | 189.7% | no |

## Normalized same-allocation ratios

`estimate(target) / estimate(control)` using the same estimator on both sides. The control is generic, not a frozen copy of the production operation. CPU and storage response need not match.

| Target/control | Estimator | Train max error | Original holdout max error | Candidate e | Meets original screen |
|---|---|---:|---:|---:|---|
| policy_p1/cpu_p1 | first | 8.4% | 15.1% | 13.4% | no |
| policy_p1/cpu_p1 | mean | 10.9% | 15.0% | 15.9% | yes |
| policy_p1/cpu_p1 | median | 9.1% | 14.5% | 14.1% | no |
| policy_p1/cpu_p1 | minimum | 8.3% | 18.4% | 13.3% | no |
| policy_p2/cpu_p2 | first | 23.5% | 67.5% | 28.5% | no |
| policy_p2/cpu_p2 | mean | 14.1% | 39.4% | 19.1% | no |
| policy_p2/cpu_p2 | median | 16.8% | 23.0% | 21.8% | no |
| policy_p2/cpu_p2 | minimum | 10.7% | 30.1% | 15.7% | no |
| policy_p4/cpu_p4 | first | 84.6% | 51.3% | 89.6% | no |
| policy_p4/cpu_p4 | mean | 35.6% | 30.5% | 40.6% | no |
| policy_p4/cpu_p4 | median | 10.9% | 34.3% | 15.9% | no |
| policy_p4/cpu_p4 | minimum | 7.0% | 5.8% | 12.0% | yes |
| policy_p1/sha256 | first | 6.7% | 40.9% | 11.7% | no |
| policy_p1/sha256 | mean | 7.7% | 39.5% | 12.7% | no |
| policy_p1/sha256 | median | 7.0% | 38.6% | 12.0% | no |
| policy_p1/sha256 | minimum | 8.1% | 39.2% | 13.1% | no |
| policy_p1/files_warm | first | 44.7% | 44.9% | 49.7% | no |
| policy_p1/files_warm | mean | 45.5% | 44.9% | 50.5% | no |
| policy_p1/files_warm | median | 45.4% | 44.5% | 50.4% | no |
| policy_p1/files_warm | minimum | 45.8% | 45.0% | 50.8% | no |
| sqlite_full/cpu_p1 | first | 5478.3% | 7566.3% | 5483.3% | no |
| sqlite_full/cpu_p1 | mean | 2014.9% | 2664.1% | 2019.9% | no |
| sqlite_full/cpu_p1 | median | 197.1% | 156.0% | 202.1% | no |
| sqlite_full/cpu_p1 | minimum | 233.2% | 126.8% | 238.2% | no |
| sqlite_full/files_warm | first | 5834.7% | 8290.8% | 5839.7% | no |
| sqlite_full/files_warm | mean | 2108.7% | 2812.8% | 2113.7% | no |
| sqlite_full/files_warm | median | 147.9% | 191.5% | 152.9% | no |
| sqlite_full/files_warm | minimum | 108.9% | 127.2% | 113.9% | no |

## Selection and interpretation

The physical minimum is one actual full correct completion on that worker. The ratio of minima need not describe one temporal pair. Taking the minimum of three ratios can instead reward an unusually slow denominator. The JSON retains each allocation's selected indices and denominator inflation to make that distinction visible. These original same-index observations were rotated among nine cases and are not close reference/candidate pairs.

A low minimum cannot establish typical latency, tail latency, or absence of intermittent product stalling. It can support a best-completion estimator under explicitly repeatable reset/cache semantics, subject to fresh validation. It does not remove permanent CPU/storage differences.

Neither arithmetic averaging nor minimum selection can turn a resource-mismatched CPU control into a storage calibration. An apparent successful row is a hypothesis for a fresh, predeclared experiment; selecting it after reading this table would reuse the original holdout.
