# #64 paired-reference calibration experiment, v2

This is a finite experiment, not adoption of #64, a new gate, or a claim about
Riverhog/Fishhat performance. The prior 24-worker dataset is exploratory input;
none of its reused holdout results constitutes fresh validation here.

## Question and predeclared method

Can a frozen, workload-matched reference on the **same** public `ubuntu-24.04`
worker cancel hardware variation sufficiently to make a small CI performance
comparison useful? Does minimum-of-three improve robustness while retaining
sensitivity to actual added work? Where does that estimator hide product cost?

The **primary estimator is the ratio of minima**, `min(C1,C2,C3)/min(R1,R2,R3)`.
It is not the minimum of three C/R ratios: that can reward an unusually slow
reference. Also report first/first, mean/mean, median/median, and raw timings as
predeclared diagnostics; do not promote an alternative on this same holdout
without explicitly labeling that choice exploratory.

24 new workers run the same frozen source: IDs 1–12 fit, then IDs 13–24 validate
in a dependent second job matrix. For each workload's unchanged A/A comparison,
`e = max(abs(ratio - 1))` over fit workers plus **3 percentage points**. The
maximum acceptable pilot allowance is **20%**. Require every holdout A/A ratio
within that fixed allowance. Do not recenter the expected ratio away from 1,
discard workers, widen the allowance, or rerun successful jobs for a nicer result.
Report fit/holdout extremes, all failures, hardware/resource strata, elapsed
harness cost, and raw/minimum/mean/median ranges. This is a finite empirical
screen, not a confidence interval or proof of a low long-term false-alarm rate.

Sensitivity is a **separate** screen: in every holdout, the persistent +50% work
case should exceed **1.20 times** its same-workload reference. Extra work need
not mean +50% elapsed time, especially for tiny parallel cases with fixed pool
startup. Report that limitation, rather than changing the threshold. Also report
the more conservative classification against an illustrative fixed budget of
1.20 reference units using `ratio/(1+e)` and `ratio/(1-e)`. An unchanged pass plus
an added-work budget miss is stronger evidence than sensitivity alone. Neither
1.20 nor the pilot e cap is an adopted project budget.

No environment-based rejection is introduced in this first v2 screen. Wrong
source/runtime/CPU count or failed verification fails collection; other noisy
workers remain visible. If reference stability rules are suggested after this
run, report their exclusions and treat them as a new hypothesis requiring fresh
validation. The two waves are temporally ordered, but close together: this is
not validation across days or weekly image updates.

## Actual timed work and controls

- `policy16_p1/p2/p4`: sixteen independently prepared repository workflow fixtures
  checked by the real frozen `all_policy.protocol.check_repository`. The p2/p4
  outer process pool is experimental, not an existing product concurrency mode.
- `policy512_p1/p2/p4`: the same sixteen fixtures, 32 complete traversals. Report
  the 512-check window, never call its amortized rate a cold 16-member result.
- `files4096`: 256 traversals of sixteen warm 4 KiB files, including directory
  enumeration, stat, read, and checking. Increased-work case does 384 traversals.
- `sqlite64`: new SQLite rollback-journal database, `synchronous=FULL`, schema
  creation plus 64 separately committed inserts and close. Added-work case
  performs 32 additional commits (mutate then restore sixteen rows); both yield
  the same independently verified final rows. API behavior is measured, **not**
  physical persistence or power-loss guarantees. New files for every execution;
  post-timer verification and reset are outside the declared completion boundary.
- For each family, run unchanged reference/candidate A/A, then candidate-only
  +50% processing/visits or commits. Both sources are byte-identical at the frozen
  product base; the added-work injection lives only in the experimental harness.
- `policy16_p1/wait_each`: candidate has 64 ms required wait every execution.
  `wait_once`: candidate has it on the middle of its three executions. This is an
  intentional adversarial demonstration: a fastest-run gate may erase recurring
  cost. The delay is included in wall time, not subtracted in analysis.
- `reference_wait_once/reference_wait_each`: inject the same 64 ms delay in the
  **reference only** on one/all executions. This tests denominator contamination.
  These are adversarial diagnostics, not observations to silently reject.
- `cycle48`: time three complete sixteen-member operations in one window. The
  candidate `wait_cycle` includes one 64 ms wait in every window, showing how
  defining a complete work cycle can expose the periodic cost even to a minimum.
- `cold16`: a fresh interpreter imports the real protocol and checks sixteen
  fixtures in an experimental wrapper. Process startup/exit are timed. This is
  process-cold with warm prepared files, not a cold filesystem or product CLI.

Every family has three reference/candidate pairs, executed adjacently with
counterbalanced A/B ordering. Case order rotates/reverses by allocation/repeat.
Reference and candidate use distinct fixture directories. Pool startup, dispatch,
collection and shutdown, database create/commit/close, and injected waits are
inside their timers. Fixtures and independent verification are outside. No
garbage-collection disabling, CPU-time substitution, concurrent benchmark cases,
adaptive repetition count, sample trimming, or work omitted for timing convenience.

## Independence, reference anchor, and limitations

Both product trees are frozen at `03de186a044c9c6b365347485a6c4093ce831c79`.
The reference is a separate checkout, its loaded protocol module has an
independent identity, and fixture/protocol hashes are retained. Python 3.11.9
and PyYAML 6.0.3 are pinned; this experiment changes neither. It does **not** test
an upgrade of the candidate runtime/dependency against an independently packaged
old runtime. A real adapter must keep those reference dependencies independent.

For an absolute reference-equivalent display, freeze `A` from the median of fit
workers' reference statistics for each family. Then `equivalent_ms=A*ratio`.
Here the ratio has expected value 1 by A/A construction, so no fitting to candidate
performance is permitted. An actual authoritative budget must be chosen from
operator requirements and independent attainable performance, not automatically
from the current implementation. These experimental anchors are not usability
targets or fixed-hardware latency claims. They are fixed before the designated
holdout is interpreted and can differ by estimator.

Matched references test cancellation under the sampled workloads. A future
candidate changing its CPU/storage/waiting mixture can invalidate transfer.
Persistent and intermittent wait and commit controls make this limit explicit.
Raw end-to-end operator latency still needs its own representative qualification.

## Reproduction and provenance

The branch-only workflow `.github/workflows/calibration-paired-64.yml` is a finite
push-triggered experiment. Source/report commits do not alter `main`, consumer
repos, schedules, credentials, or required gates. Results-only publication does
not trigger it. `python experiments/64/v2/paired.py N --smoke` validates harness
mechanics locally and is explicitly excluded from CI qualification. Production
verification and a deliberately invalid input are checked on every worker.
All raw observations and original job/artifact identifiers will be retained.
