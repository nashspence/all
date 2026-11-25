# #64 frozen reference guard: fresh v3 validation

[Actions run](https://github.com/nashspence/all/actions/runs/45682545450) at `2f1a2f6406f8f7d52592cb95a693483cc111c838`. All 24 allocations validate a fixed rule fitted from the previous v2 campaign. The old `fit`/`holdout` labels in raw records are harness metadata only; no fresh observations fit this rule. All 3,456 timings remain retained.

## Fixed decision

Reference agreement: max(Rcase,Raudit)/min(Rcase,Raudit)−1≤10%, using each reference's minimum of three. Score=min(candidate)/min(Rcase,Raudit). The faster reference is the denominator. The fixed error allowance and reference anchor are in guard_config.json; the allowance is never widened or clamped. At least 23/24 cohorts must be eligible in both unchanged and +50%-work cases. Every eligible unchanged score must remain within its fixed allowance and support a conservative pass against 1.20; every eligible work score must support a miss. A mismatch fails the screen; it is not discarded as noise.

| Family | Scope | Fixed e | Eligible null /24 | Eligible work /24 | Reference reproducibility | All eligible null budget pass | All eligible work miss | Combined |
|---|---|---:|---:|---:|---|---|---|---|
| policy16_p1 | primary | 10.0% | 24 | 24 | pass | yes | yes | pass |
| policy16_p2 | secondary | 29.7% | 18 | 18 | fail | no | no | fail |
| policy16_p4 | secondary | 10.9% | 24 | 24 | pass | yes | no | fail |
| policy512_p1 | primary | 4.5% | 24 | 24 | pass | yes | yes | pass |
| policy512_p2 | primary | 10.9% | 24 | 24 | pass | yes | yes | pass |
| policy512_p4 | primary | 6.4% | 24 | 24 | pass | yes | yes | pass |
| files4096 | primary | 5.9% | 24 | 24 | pass | yes | yes | pass |
| sqlite64 | secondary | 53.1% | 18 | 18 | fail | no | no | fail |
| cycle48 | secondary | 5.9% | 24 | n/a | pass | yes | n/a | n/a |
| cold16 | secondary | 5.5% | 24 | n/a | pass | yes | n/a | n/a |

Primary reference reproducibility: **5/5 pass**. Stronger combined budget/detection screen: **5/5 pass**. An overlap with the illustrative budget is distinct from failed reference reproducibility; it indicates insufficient budget headroom under this decision rule. Secondary failures do not become qualified by passing a primary family.

## Adversarial checks

| Check | Eligible/rejected result | Predeclared outcome |
|---|---|---|
| Persistent reference-only delay | 24/24 rejected | pass |
| One delayed reference repetition | 24/24 eligible; 0 eligible nonpasses | pass |
| Complete cycle with recurring wait | 24/24 eligible; 0 eligible nonmisses | pass |

## Failures and unestablished cohorts

All excluded allocation IDs and exception observations are retained in guard_analysis.json. These are unavailable measurements, not passes. The table below separates guard rejection from a score that the guard admitted but the fixed decision could not accept.

| Case | Guard-ineligible allocations | Admitted null allowance misses | Admitted wrong/overlap classification |
|---|---|---|---|
| policy16_p2/same | 5, 14, 16, 17, 21, 24 | none | 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 15, 18, 19, 20, 22, 23 |
| policy16_p2/work50 | 5, 14, 16, 17, 21, 24 | none | 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 15, 18, 19, 20, 22, 23 |
| policy16_p4/work50 | none | none | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24 |
| sqlite64/same | 2, 3, 5, 7, 8, 20 | none | 1, 4, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24 |
| sqlite64/work50 | 2, 3, 5, 7, 8, 20 | none | 1, 4, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24 |
| policy16_p1/reference_wait_each | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24 | none | none |

## Scope and reproduction

Harness median 10.84s per allocation, range 10.46–17.73s, excluding Actions setup/upload. The operation cases are unchanged from v2, including all startup, commits, output checking and injected waits described there.

- Every allocation is fresh validation against coefficients frozen from all 24 v2 allocations.
- No v3 fit, recentering, allowance widening, estimator selection or post-hoc exclusions.
- Ineligible cohorts remain unestablished and count against declared availability.
- Null score mismatch is a failed calibration prediction, not an environmental rejection.
- A guard validates reference agreement, not reference equivalence to a physically fixed machine.
- Shared contamination of both references and changed candidate resource mixtures remain transfer limitations.
- Minimum still does not establish typical or tail latency; complete recurring work must lie inside every timed window.
- This short finite campaign cannot estimate long-term false-alarm probabilities or image-update transfer.

Run `python experiments/64/v3/analyze_guard.py` to reproduce the result. The analyzer reuses v2's exact-source/fixture/runtime/completeness checks and does not refit. The reference configuration can be reproduced from the retained v2 data with `build_guard_config.py`; it must not be rebuilt from v3 observations. This is an experiment, not adoption of #64 or Riverhog/Fishhat qualification.
