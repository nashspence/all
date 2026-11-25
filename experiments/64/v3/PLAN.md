# #64 guarded-reference follow-up: predeclared fresh validation

This final bounded follow-up addresses two concrete limits of v2: a persistently
slow reference can falsely improve a ratio, and the small SQLite commit case did
not calibrate. No policy, consumer contract, product budget or gate is adopted.

## Guarded reference mechanism

For a candidate case, run three complete candidate executions and two disjoint
cohorts of three frozen-reference executions. They perform the same reference
work on the same worker. Let `C`, `R1`, and `R2` be the three cohort minima.

- Guard: `max(R1,R2)/min(R1,R2) - 1 <= 0.10`.
- Score: `q = C/min(R1,R2)`; this conservative denominator cannot select the
  slower of the reference cohorts to make the candidate look faster.
- A failed guard means **unestablished**, not a pass and not evidence of a product
  regression. Preserve it and include it in the availability denominator.
- Keep the reference anchor, allowance and budget frozen. The reference's source,
  dependencies, fixture, execution mode and completion boundary are independent
  of candidate changes. A runtime or dependency change needs an independently
  packaged old reference; this campaign keeps both pinned versions unchanged.

Ten percent is selected from the completed v2 exploration and is frozen for
this **new** validation. It is not qualified by retrospectively filtering v2.
The guard detects localized reference degradation. Equal contamination of both
reference cohorts remains a limitation; this is not a universal worker-speed
meter or proof that all elapsed-time components scale identically.

## Fresh campaign and frozen decisions

Run the unchanged v2 `paired.py` measurement harness on **24 additional public
ubuntu-24.04 workers**, in two successive twelve-worker matrices. It retains all
24 case combinations and three adjacent candidate/reference pairs. The existing
record phase labels `fit` and `holdout` describe the inherited harness numbering;
**all 24 v3 workers are new validation**, and no v3 values fit the mechanism.

Reference audits reuse independently executed reference observations already
present in the experiment, with no candidate result used as a denominator:

- For each non-`same` case, the audit is that family's `/same` reference cohort.
- For `/same`, the audit is `/work50`'s reference cohort, which performs no added
  work. For `cycle48/same` use `/wait_cycle`'s reference; for `cold16/same` use
  `/wait_each`'s reference. Only their candidates contain those delays.

The complete v2 dataset fits one fixed allowance per family:
`e = max(abs(q_null - 1)) + 0.03`, with the same 20% cap. The reference anchor is
the median v2 value of `min(R1,R2)`. Exact values and source/fixture identities
are recorded in `guard_config.json` before the new workflow runs. No centering,
threshold revision, rerun of successful jobs, or omitted worker is allowed.

Primary families were the five with strong v2 evidence: serial16, serial512,
parallel512 at2/4, and warm file work. Every other case remains reported as a
secondary diagnostic; known tiny-p2 and SQLite failures cannot become passes by
being left out of the report.

For each primary family, separately require:

1. At least **23/24** new workers have valid reference agreement for both null
   and added-work comparisons. Report the exact count; this modest finite
   availability screen is not a long-term service-level guarantee.
2. Every reference-qualified null score remains within its frozen allowance.
3. Every reference-qualified null supports a conservative budget pass and every
   reference-qualified +50%-work case supports a budget miss against the unchanged
   **illustrative** `B=1.20` reference units: `upper=q/(1-e)` and `lower=q/(1+e)`.
   Report reproducibility, reference availability and budget headroom separately.
   In particular, a near-boundary overlap is unestablished, not a falsely declared
   regression. Do not increase the illustrative budget after seeing an overlap.

The persistent reference-only64ms delay must be rejected on24/24workers. The
single-reference-delay case must retain at least23/24availability with all
admitted null scores conforming. The complete-cycle candidate delay must retain
at least23/24availability and every admitted result must establish a budget miss.
The one-delayed-candidate-repeat remains an explicit expected limitation of a
minimum; it is not claimed to be covered by the ordinary fast-path case.

Reference-equivalent milliseconds equal `anchor*q`; they are not raw elapsed
time or an assertion of operator latency on all machines. A project must set
its real budget from operator requirements and independently attainable speed.
The additional reference cohort increases routine measurement cost from six to
nine complete executions per case; retain total harness work as well as minima.

## Narrow storage extension

An independent twelve-worker matrix runs `storage.py` for64,256,1024commits with
full create/commit/close completion and verified equivalent final rows. Its own
predeclared fit/validation rule, sample extent and runtime bound are documented
in `STORAGE_PLAN.md`. It asks whether larger complete commit windows improve the
failed small storage result, without removing persistence work from the timer.
It cannot establish physical durability or individual-commit tail latency.

## Scope and stopping

This is one finite follow-up, not calibration until green. Preserve all outcomes,
including guard rejections, noisy classes and any storage incompleteness. Raw
timings remain available. Future image/date coverage and smaller regression doses
are separate evidence needed before a required production gate. `main`, Riverhog
and Fishhat remain unchanged. The branch-only workflow has no schedule; analysis
and report publication do not retrigger it.
