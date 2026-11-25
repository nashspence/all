# #64 v4: raw wall-clock budgets and central profile admission

[Actions run](https://github.com/nashspence/all/actions/runs/45692367319) at `ce6c39ce904c13aa8e6d5a6c619b6d2f35d47a58`; independent authority `3c88f1b3bf28b4fe5ae8973ff40412be1c049952`. All 24 workers are fresh validation; no observations fit or adjust budgets, probe ceilings or acceptance. Retained evidence contains 2,232 product timings and 1,440 generic probe timings. Analysis recomputes all admissions and decisions from the pinned source and contract.

## Profile availability and impairment controls

| Profile | Preflight admitted /24 | Availability ≥23/24 | Postflight admitted /24 (diagnostic) | CPU-pressure rejected /24 | One-CPU rejected /24 |
|---|---:|---|---:|---:|---:|
| core | 24 | pass | 24 | 24 | 24 |
| sync | 22 | fail | 22 | 24 | 24 |

CPU-pressure sensitivity screen: **pass**. One-CPU rejection screen: **pass**. A busy worker satisfying every fixed ceiling still satisfies the declared profile. Postflight and later impairment results never rewrite preflight admission or product verdicts.

## Fixed raw operation budgets

Every one of the three raw observations must fit B. Mixed misses block acceptance. Minimum is shown only to reveal observations that a minimum-based rule would hide.

| Operation | B ms | Profile | Admitted | Strict pass | Mixed miss | All over | Unqualified | Minimum would pass | Usefulness screen |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| policy16_p1 | 20 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| policy16_p2 | 30 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| policy16_p4 | 30 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| policy512_p1 | 500 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| policy512_p2 | 350 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| policy512_p4 | 300 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| cycle48 | 50 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| cold16 | 125 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| copy16 | 20 | core | 24 | 24 | 0 | 0 | 0 | 24 | pass |
| copy16_sync | 100 | sync | 22 | 21 | 1 | 0 | 2 | 22 | fail |
| sqlite64 | 150 | sync | 22 | 16 | 6 | 0 | 2 | 22 | fail |

Passing operation/profile pairs: **9/11**. policy16_p1, policy16_p2, policy16_p4, policy512_p1, policy512_p2, policy512_p4, cycle48, cold16, copy16

A failed row is not repaired by adjusting B or dropping workers. An admitted raw miss is a measured budget miss, not proof of its cause. Resource admission and actual operation conformance are separate claims.

## All additional cases

Wait means an actual B+16 ms delay; extra50 means additional processing and may legitimately pass an absolute budget. Periodic wait affects one repetition; cycle wait lies inside every complete cycle. All values below use binding preflight admission.

| Case | Pass | Mixed miss | All over | Unqualified | Minimum would hide miss |
|---|---:|---:|---:|---:|---:|
| policy16_p1/wait | 0 | 0 | 24 | 0 | 0 |
| policy16_p2/wait | 0 | 0 | 24 | 0 | 0 |
| policy16_p4/wait | 0 | 0 | 24 | 0 | 0 |
| policy512_p1/wait | 0 | 0 | 24 | 0 | 0 |
| policy512_p2/wait | 0 | 0 | 24 | 0 | 0 |
| policy512_p4/wait | 0 | 0 | 24 | 0 | 0 |
| cycle48/wait | 0 | 0 | 24 | 0 | 0 |
| cold16/wait | 0 | 0 | 24 | 0 | 0 |
| copy16/wait | 0 | 0 | 24 | 0 | 0 |
| copy16_sync/wait | 0 | 0 | 22 | 2 | 0 |
| sqlite64/wait | 0 | 0 | 22 | 2 | 0 |
| policy16_p1/extra50 | 24 | 0 | 0 | 0 | 0 |
| policy16_p2/extra50 | 24 | 0 | 0 | 0 | 0 |
| policy16_p4/extra50 | 24 | 0 | 0 | 0 | 0 |
| policy512_p1/extra50 | 24 | 0 | 0 | 0 | 0 |
| policy512_p2/extra50 | 23 | 1 | 0 | 0 | 1 |
| policy512_p4/extra50 | 23 | 0 | 1 | 0 | 0 |
| policy16_p1/periodic_wait | 0 | 24 | 0 | 0 | 24 |
| policy16_p1/override_wait | 0 | 0 | 24 | 0 | 0 |
| cycle48/cycle_wait | 0 | 0 | 24 | 0 | 0 |

Every record confirms the candidate manifest was actually changed, the separate authority remained unchanged, proposed budgets did not activate, and later probes could not rewrite decisions. The override case's fabricated elapsed time/profile/budget are rejected while the trusted outer clock remains decisive. This demonstrates the experiment's source boundary; real repository approval permissions still require their normal protected-review arrangement.

The candidate adapter is imported and its fixtures are constructed before preflight. Preflight precedes the timed product calls, not all candidate code. The adapter also executes in the timer's Python process: this is not isolation against arbitrary candidate code or monkeypatching. The tested controls cover ordinary manifest/claim overrides; owning-contract review must still bind fixtures, entrypoints and completion to the intended operation.

## Failure and unavailability IDs

- core preflight rejected: none. Preflight admitted then postflight rejected: none.
- sync preflight rejected: 2, 23. Preflight admitted then postflight rejected: 8, 21.

| Case | Mixed-miss IDs | All-over IDs |
|---|---|---|
| copy16_sync/normal | 21 | none |
| sqlite64/normal | 1, 3, 8, 10, 18, 21 | none |
| policy512_p2/extra50 | 2 | none |
| policy512_p4/extra50 | none | 2 |

Full per-case verdict IDs, all admission reasons and probe ranges are retained in analysis.json; all raw samples remain in observations.json. Unqualified cohorts are unavailable evidence, not passes.

## Raw unchanged timing and measurement cost

All raw samples, including nonadmitted workers, are included in these ranges. These are complete declared observations; a 512-check window is not a cold 16-member latency estimate.

| Operation | Raw min ms | Raw max ms |
|---|---:|---:|
| policy16_p1 | 6.136 | 10.495 |
| policy16_p2 | 8.744 | 19.503 |
| policy16_p4 | 9.784 | 19.571 |
| policy512_p1 | 197.129 | 314.539 |
| policy512_p2 | 138.543 | 246.904 |
| policy512_p4 | 118.957 | 215.924 |
| cycle48 | 18.887 | 29.588 |
| cold16 | 31.940 | 46.148 |
| copy16 | 0.292 | 0.919 |
| copy16_sync | 3.682 | 710.579 |
| sqlite64 | 28.793 | 1318.996 |

Sum of timed preflight probe calls: median 1.41s (core-only calls 1.36s); this excludes probe preparation and verification. Whole experimental harness: median 22.26s, range 20.87–31.23s, excluding Actions setup/upload. The full diagnostic campaign also performs postflight, CPU-pressure and one-CPU controls; these are not proposed per-operation overhead.

## Scope and reproduction

These are experimental numbers, not approved product budgets. The experiment does not fit tolerances, normalize time, use a project reference implementation, or establish physical durability. Parallel wrappers and the process-start case are experimental adapters. A passing case establishes this finite raw-budget procedure on sampled workers, not universal or tail-latency bounds, future-image reliability, or Riverhog/Fishhat performance.

Run `python experiments/64/v4/analyze.py` against retained observations to reproduce this report. Source/hash, contract, runtime, observation completeness, authority mutation, fixed-wait and exact acceptance checks run before summary generation. No new workers are launched.
