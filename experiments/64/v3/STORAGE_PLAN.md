# v3: complete SQLite windows with an independent reference guard

This finite exploratory experiment follows the failed v2 `sqlite64` calibration.
It tests whether larger **complete work windows** improve calibration. It does
not change the transaction boundary, drop commits, qualify physical durability,
or alter a production project. All results, including guard rejection and timeout,
must remain visible. No successful allocation is rerun for a better result.

## Frozen workloads and collection

Twelve new public `ubuntu-24.04` allocations, numbered 1–12. IDs 1–6 fit and IDs
7–12 form the designated holdout. If these run in one concurrent matrix, the
holdout is an allocation split, **not a temporally independent confirmation**.
Python 3.11.9 and the exact workflow source commit are checked. SQLite version,
CPU model, affinity, kernel, filesystem and image version are retained.

Each observation creates a new SQLite database in `RUNNER_TEMP`, selects DELETE
rollback journaling and FULL synchronization, creates a schema, commits 64, 256
or 1024 individual 4 KiB inserts, and closes the connection. Creation, settings,
schema, each commit and final close are all inside the wall-clock timer. There
is no warmup observation. Each database has a distinct path.

For each extent run an unchanged candidate and a candidate with **50% more data
commits**: mutate and restore the first quarter of rows, each change committed
separately. Final rows are identical. There is one schema commit in every
observation, so the increased data-commit count is not a claim of exactly 50%
more total commits or elapsed time. Independent row and integrity verification
and removal occur after timing. Incorrect output is a collection failure.

Run three triplets per case: reference A, candidate, reference B. Reverse the
triplet direction and rotate case order by allocation and repeat. Candidate is
adjacent to both references; A and B are separate complete executions on fresh
databases. They share a worker and storage system, so they are not statistically
independent machines. There are six cases and **54 timed executions per worker**,
648 if all twelve workers complete.

Collection has a 90-second monotonic deadline checked before every data commit.
An incomplete execution and all earlier samples are serialized, the process exits
nonzero, and that worker cannot qualify. The workflow should also set a 2-minute
step timeout: a stalled operating-system call cannot be interrupted by a Python
deadline check. Setup/checkouts are outside this experiment's execution budget.
Successful runs retain every complete timing. Incomplete data is never used as a
fast sample.

## Predeclared estimator and screens

The primary ratio is `min(candidate) / min(min(reference_A),min(reference_B))`.
Using six reference observations against three candidate observations is an
intentional conservative choice, not a claim of an unbiased ratio. The unchanged
A/A calibration measures its resulting deviation. An independent guard requires
`max(min(A),min(B))/min(min(A),min(B)) <= 1.10`. Do **not** pool A and B into a
single cohort when computing this agreement guard. The guard cannot detect a
slowdown common to both reference cohorts and is not a
physical-storage performance guarantee.

Report both unguarded and guarded results. Guard failure is **unestablished**,
not a pass, and contributes to the rejection/availability count. For each extent
fit `e = max(abs(null_ratio - 1)) + 0.03` on **all six fit allocations**, including
guard-rejected ones, with a fixed cap of 0.20. No recentering or larger cap is
allowed. Every eligible holdout null ratio must be within that frozen e; require at least five
of six holdout allocations eligible for each of unchanged and increased-work
cases. Report the excluded IDs and reasons beside the conditional result. These
counts are pilot screens, not a confidence bound or long-term availability claim.

Sensitivity separately requires every eligible holdout increased-work ratio to
exceed 1.20. Also report a conservative illustrative budget classification:
`ratio/(1-e) <= 1.20` is a pass; `ratio/(1+e) > 1.20` is a miss; otherwise it is
unestablished. Require a qualified e and a passing reference guard before either
classification. The stronger qualification screen also requires every eligible
unchanged holdout to pass and every eligible increased-work holdout to miss.
Report the counts rather than converting arithmetic sensitivity into budget
qualification.

The first/first, mean/mean and median/median ratios are diagnostics only. Report
all raw ranges, guard rejections, sample counts, incomplete workers and harness
cost. A qualified longer window is evidence for that window, not qualification
of a tiny 16-member operation; do not relabel an amortized rate as its latency.

The thresholds, three repetitions and extent choices are experiment parameters,
not changes to #64 authority. A result requires fresh confirmation before general
use across workload mixtures, future images or storage APIs. Persistently slow
but matched references can still normalize away genuinely poor raw performance;
raw operator completion remains a separate requirement.

## Local check

`python experiments/64/v3/storage.py 1 --smoke` runs the same extents and explicitly
tags its output as local smoke data. It verifies mechanics only and must be
excluded from GitHub Actions qualification. `storage-observation.json` and the
`STORAGE_OBSERVATION` log line retain the complete observation record.
