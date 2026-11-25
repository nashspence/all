# #64: a workable matched-reference calibration, with explicit limits

## Finding

**A frozen, workload-matched reference, measured on the same worker, combined
with minimum-of-three complete executions and an independent reference-agreement
check, passed fresh validation for five processing and warm-file workloads.**
It is a practical candidate for those classes. It is not a universal correction
for public-runner wall time, and the tested durable-write cases remain unqualified.

This investigation added **60 distinct GitHub-hosted worker allocations and
7,560 verified timing observations**, beyond the original pilot. It sampled six
CPU models. Every successful job ran once; no worker or timing was removed to
obtain a pass. Three log-retrieval failures were retried without rerunning jobs.
Raw JSON observations, source/fixture identities, job/runner IDs and uploaded
artifact metadata are retained. Observations were extracted from original job
logs; artifact ZIP payloads were not independently downloaded.

- [Initial paired experiment: 24 workers](https://github.com/nashspence/all/actions/runs/45680767861),
  source `7355aed8042e61eedc491428a063080a7f557f5b`.
- [Fresh guard validation and storage extension: 24 + 12 workers](https://github.com/nashspence/all/actions/runs/45682545450),
  source `2f1a2f6406f8f7d52592cb95a693483cc111c838`.
- Product source stayed frozen at `03de186a044c9c6b365347485a6c4093ce831c79`.
  The operation is the real local `all_policy.protocol.check_repository` on
  disposable fixtures; this is not a Riverhog publication or Fishhat operation.

The predeclared plans and reports are [v2 PLAN](v2/PLAN.md), [v2 results](v2/RESULTS.md),
[v3 PLAN](v3/PLAN.md), [v3 guard results](v3/GUARD_RESULTS.md),
[storage plan](v3/STORAGE_PLAN.md), and [storage results](v3/STORAGE_RESULTS.md).

## Why taking the minimum alone is insufficient

Reanalyzing the original pilot, the largest designated-holdout deviation for raw
serial policy timing was **64.91% using the mean and 65.21% using the minimum**.
The minimum removed some intermittent long observations, but did not correct
different machines' processing speeds. Original SQLite deviation fell from
3,776.76% to 196.49%, still far outside the 20% screen. Those long completed
operations were not proven irrelevant interference.

The mechanism must address two different things: hardware/workload differences
through a matching reference, and intermittent delays through a clearly defined
estimator. A minimum is the best observed complete execution, not the expected
latency, a maximum latency, or a guarantee about future executions.

GitHub documents public x64 Ubuntu workers as 4 CPUs, 16 GB RAM and 14 GB SSD, but does
not prescribe a CPU model or storage latency in that table. Eligible standard
Linux jobs can be scheduled on AWS or Azure with the same workflow label.
Sources: [runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and [multi-cloud scheduling](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners#cloud-hosts-used-by-github-hosted-runners).

## Mechanism that passed the fresh test

Each case has an immutable reference implementation, fixture, runtime/dependency
identity, completion boundary and reference-time anchor. Execute reference and
candidate on the same allocated worker with matching resources and state.
Verify completed outputs independently. Keep startup, required commits,
synchronization, worker shutdown and all other attributable work in the timer.

For one case collect three candidate executions and two disjoint cohorts of
three reference executions. Let `C`, `R1` and `R2` be the minimum of each cohort.

```
reference_difference = max(R1, R2) / min(R1, R2) - 1
eligible             = reference_difference <= 0.10
score                = C / min(R1, R2)
reference_equiv_ms   = fixed_anchor_ms * score
```

The faster reference is the denominator. Selecting the minimum of individual
candidate/reference ratios can choose an unusually slow denominator and falsely
make the candidate look fast; it is not the same estimator.

If the references disagree beyond the frozen guard, the result is unestablished.
The candidate running slowly cannot invalidate its environment. Guard rejections
remain in availability counts. Preserve all timings and the total measurement
cost, not only the chosen minima.

For v3, both the 10% guard and each family's error allowance were frozen from v2
before the new workers ran. The allowance was the largest v2 unchanged-score
deviation plus three percentage points, with a 20% cap. No v3 observation fitted
or widened it. The illustrative fixed budget was 1.20 reference units; a pass
required `score/(1-e) <= 1.20`, and a miss required `score/(1+e) > 1.20`.
Overlaps were unestablished. These are empirical decision bands, not statistical
confidence intervals, and the illustrative numbers are not product design targets.

## Fresh validation result

All five predeclared primary families admitted **24/24** unchanged cohorts and
**24/24** added-work cohorts. Every unchanged result supported a conservative
budget pass; every deliberately increased-work result supported a budget miss.
No primary-family worker needed exclusion or a larger allowance.

| Workload | Frozen allowance | Largest fresh unchanged error | Observed +50%-work score | Median nine-execution measurement cost |
|---|---:|---:|---:|---:|
|16 serial policy checks|9.96%|6.50%|1.515–1.559|70.2 ms|
|512 serial policy checks|4.52%|1.40%|1.492–1.525|2.170 s|
|512 checks, 2 processes|10.91%|3.03%|1.462–1.542|1.452 s|
|512 checks, 4 processes|6.43%|4.98%|1.430–1.520|1.321 s|
|Warm enumeration/stat/read work|5.94%|2.39%|1.488–1.524|0.345 s|

The 512-check case is 32 complete traversals of 16 fixtures. Its rate is not a
separately measured cold 16-member latency. Process-pool parallelism is an
experimental wrapper, not an existing product concurrency feature.

Raw serial 512 candidate minima varied from 199.06 to 393.41 ms between workers,
while calibrated unchanged scores stayed within1.40% of 1. The serial 16
candidate minima ranged 6.45–12.68 ms; the full nine-execution measurement cost
was about 70 ms at the median. The whole diagnostic harness took a median 10.84 s
per fresh worker, excluding Actions setup and upload. The extra reference cohort
is real CI work; it is not free merely because the experiment already collected it.

The first fresh experiment directly compared statistics under the same screen:

| Estimator | Unchanged calibration passes /10 | Strong unchanged-pass plus added-work-miss families /8 |
|---|---:|---:|
|Minimum of 3|8|5|
|Arithmetic mean of 3|6|3|
|Median of 3|6|4|
|First execution|4|2|

Minimum was chosen as the primary estimator before that holdout. The other
statistics are diagnostics, not alternatives selected after a failed result.

## Two important traps, tested explicitly

**A slow reference can manufacture apparent improvement.** In v2, inserting 64 ms
into every reference execution reduced the median minimum ratio to 0.106 even
though the candidate was unchanged. On fresh v3 workers, the second reference
cohort and fixed agreement guard rejected all 24 contaminated cases. An isolated
slow reference repetition was tolerated on all 24, with no false candidate miss.

The guard cannot detect the same contamination in both reference cohorts. Frozen
independent source/dependencies and workload applicability are essential. A
candidate that changes its CPU/storage/waiting mixture may require a new model.

**A minimum can erase recurring product cost.** Inserting one 64 ms candidate wait
among three observations produced a median minimum ratio of 1.018, while the
mean ratio was 3.715. The minimum treated the recurring wait as if it did not
matter. The analogous case that forced one 64 ms wait inside *every complete
three-operation window* exposed the cost. All 24 fresh guarded comparisons
detected that complete-cycle delay as a budget miss.

Therefore a minimum-based ordinary-operation case needs named witnesses for
periodic checkpoint/flush/compaction work, cold setup, and relevant thresholds.
Every observation of those witnesses must contain the work. A 48-member cycle
has its own declared extent and budget; dividing its duration by 3 does not
establish 16-member startup latency or tail latency.

## Storage and tiny parallel operations remain limited

The small SQLite 64-commit case failed calibration. A separate twelve-worker
experiment tested 64, 256 and 1,024 individually committed inserts, three bracketed
reference/candidate/reference triplets per case, with final rows and integrity
verified. Increased-work cases added 50% more data commits while restoring the
same final rows. No commits or synchronization settings were removed.

| Commits per complete observation | Fitted allowance | Eligible unchanged holdouts | Eligible added-work holdouts | Strong screen |
|---|---:|---:|---:|---|
|64|14.82%|5/6|4/6|Unestablished|
|256|11.67%|5/6|6/6|Unestablished|
|1024|10.84%|4/6|5/6|Unestablished|

The 256 case improved conditional reproducibility and detected all six added-work
cases, but only two of five eligible unchanged results supported a conservative
budget pass. The 1,024 case failed availability and left one admitted increased-work
result unestablished. All raw unchanged 1,024-commit executions spanned 315.67 ms
to 4.777 s; minimum-based summaries do not describe that operator-visible range.

This is a negative result for the tested procedure and thresholds, not proof
that all hosted storage calibration is impossible. It does not qualify physical
durability, other database modes, real uploads, or recovery performance.

The 16-check p2 wrapper also remained unqualified. The p4 wrapper reproduced
unchanged timing but did not meet the +50%-processing sensitivity screen:
fixed pool startup dominates so 50% more processing is not 50% more elapsed time.
The small parallel cases actually completed more slowly than serial. Preserve
that evidence when designing parallelism targets; do not assume linear speedup.

## Recommended policy revision

1. **Remove the universal arithmetic-mean-of-three prescription.** Each declared
   metric needs a predeclared estimator matching its claim. Minimum-of-three
   complete executions is a supported option for a qualified execution-cost
   case. It does not certify typical or worst-case responsiveness.
2. **Allow a common matched-reference protocol with project-specific references.**
   Keep anchors, workloads and allowances under design authority, independent
   of candidate changes. Publish raw times, reference-equivalent times, all
   observations, guard results and total measurement work. Do not auto-rebase
   to a slow implementation or raise a budget to make it pass.
3. **Require complete-cost witnesses.** Force periodic production costs into
   every observation of an appropriate named case, with its own budget. Keep
   small integrated workflows and large real end-to-end qualification.
4. **Separate the metric's promises.** Reference-equivalent milliseconds can
   enforce a stable design budget across heterogeneous workers; they are not
   literal elapsed milliseconds for every operator. Absolute raw operator-time
   claims still need their declared real qualification environment and workflow.
5. **Qualify each resource/workload class before enforcement.** Require unchanged
   and deliberately slowed witnesses, fresh validation, availability reporting,
   frozen error conventions and periodic drift checks. Retain failed classes as
   unqualified. CPU/warm-file success cannot qualify persistence or networking.
6. **Keep adoption finite and economical.** The shared contract can be small;
   this diagnostic matrix need not run on every PR. The routine case is nine
   complete executions unless a smaller validated design can share reference
   work. This experiment's 24/12-worker campaigns are calibration evidence, not
   a new per-PR matrix or an ongoing schedule.

Before a required production gate, validate later dates/image revisions and
relevant near-budget regressions. Both fresh campaigns here occurred in one
short session; zero observed false alarms is not a long-term failure-rate bound.
Keep ordinary wall-time and end-to-end evidence visible so a favorable normalized
score cannot conceal unusable actual completion.

No implementation was merged into `main`, and neither Riverhog nor Fishhat was
changed. These results support revising the proposal and a scoped implementation
pilot, not declaring every repository or public-runner resource class qualified.

## Reproduce

```
python experiments/64/v2/old_analysis.py
python experiments/64/v2/analyze.py
python experiments/64/v3/analyze_guard.py
python experiments/64/v3/analyze_storage.py
```

These commands analyze retained observations. They do not launch new workers.
The original sources, frozen guard configuration, data and result files accompany
this report on the isolated `experiment/64-runner-calibration` branch.
