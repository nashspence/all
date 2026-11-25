# Proposed direction

**Maintainer-requested policy proposal; not yet adopted or implemented.** Require fixed **raw wall-clock budgets attached to shared abstract execution profiles**, measure small real production operations in ordinary CI, and require separate large end-to-end qualification before release. Durability designs remain project-owned.

This revision replaces the previous mean/error-band and matched-reference directions. It requires no project reference implementation, reference-time anchor, normalized time, percentage calibration model or alternate minimal executor. Design supplies numbers and profile choices for existing product operations. Integration implements the product and connects its real operation to the common measurement procedure.

The [v4 experiment](https://github.com/nashspence/all/tree/experiment/64-runner-calibration/experiments/64/v4) demonstrated this procedure on 24 fresh public workers: all nine tested core operation/profile pairs passed; the two synchronization-dependent pairs did not qualify. See its `RECOMMENDATION.md`, `RESULTS.md` and retained raw data. This is evidence for the proposed direction, not general storage qualification or adoption in Riverhog or Fishhat.

## 1. Independent authority with a small project contract

Correctness alone does not establish useful performance at the intended scale. Each executable project maintains a finite inventory of material operations whose cost grows with input or whose responsiveness matters. Non-executable repositories can declare this inapplicable.

| Owner | Responsibility |
| --- | --- |
| Project design | Set raw wall-clock limits and choose shared profiles for named operations and release scenarios. Approve explicit changes to these requirements. |
| Shared `all` authority | Define/version general profiles, generic admission probes and ceilings, the clock, observation rule, evidence validation and acceptance. Validate profiles through finite independent-worker campaigns. |
| Integration | Invoke the actual production operation through a thin adapter, reuse existing correctness fixtures/checks, verify completion, retain evidence and change the implementation to meet the requirement. |

The operation's existing product contract gives its meaning. Ordinary owning-contract review binds the adapter to that operation, its canonical input extent, supported configuration and completion promise. Design is not required to implement benchmark fixtures, a second algorithm, a competing tool, an oracle or project-specific calibration code. Where the intended operation is not yet defined, clarify its product semantics before claiming to measure it.

The numerical contract can be a small table: operation, profile, maximum milliseconds; collection operations normally have separate entries for parallelism 1, 2 and 4. Derive limits from intended operator use and the required capability, with useful engineering headroom. Do not automatically derive an accepted limit from today's implementation or accept seconds of per-item work merely because it is correct.

Integration cannot activate its own proposed budget, profile, timer or acceptance changes. The designated gate resolves those from independently approved, versioned authority through the existing protected review/required-check path. Merely putting them in separate files in an editable candidate checkout is insufficient. Fixture extent, input distribution, timed boundaries and configuration cannot be weakened as incidental test maintenance; material changes require the normal owning-contract decision. This is an authority and review requirement, not a demand for a second implementing agent.

A valid budget miss prevents acceptance of the affected operation/behavior or architecture until corrected or deliberately redesigned. Unqualified or missing evidence cannot earn acceptance. Corrective experiments and unrelated work can continue without pretending that missing qualification exists. Timing cannot waive correctness, security, custody, acknowledged-data or recovery obligations.

## 2. Small, complete production measurements

Use the smallest meaningful real operation for recurring CI. It must produce an independently verifiable useful result through the actual supported code/configuration. A helper omitting the operation's coordination, progress, persistence or completion cannot qualify that operation.

The common outer clock measures declared start through all work needed for the promised result: attributable production setup, dispatch, output, configured reporting, required durable commits, synchronization, child-process completion and resource release. Fixture construction and independent verification can be outside where their role is explicit. Product-required work cannot be relabeled as preparation. For asynchronous APIs, separately measure response and completion/drain promises as applicable; a quick acknowledgement cannot hide accumulating unfinished work.

### Canonical extent

- **Collection operations:** default to the same 16 members at parallelism 1, 2 and 4, with separate raw budgets. Reuse ordinary product fixtures and fix member shape, state/history, backend and reset/cache conditions. Sixteen is a measurement extent, not a product limit or required batch size.
- **Other operations:** measure one meaningful bounded unit, such as a query, configuration application or stream segment. Do not manufacture a list abstraction.
- Different extents or unavailable concurrency need an explicit domain/resource reason. Do not add parallel features to inherently serial products just for this policy. Check actual assigned resources and supported worker/thread settings.
- Where useful parallel speedup is a product promise, design can express it through appropriately tighter time limits for the declared parallel workloads. Tiny inputs can legitimately have startup overhead and no speedup expectation; use one appropriate larger bounded case for a larger-workload scaling promise. There is no compulsory separate percentage formula.
- Add only the cases necessary to expose distinct material cost regimes, such as batching, periodic commits, pages or compaction. A witness for periodic work must include that work inside the timed complete operation. Sixteen inputs do not establish large-input growth; [#20](https://github.com/nashspence/all/issues/20) retains its distinct complete-work scope.

### Observation rule

Run each canonical case **three complete times** under predeclared reset conditions. **Every raw elapsed time must be at or below the unchanged approved budget.** Keep all three values and correctness outcomes. A mean or minimum can be reported diagnostically but cannot clear an observed violation. This is a finite empirical requirement, not a mathematical maximum or tail-probability guarantee.

If a unit is too short for useful measurement, a fixed repetition of the complete unit can define an explicitly budgeted observation. Preserve all normally recurring costs and its reset semantics. Report the whole window; an amortized rate is not a measured cold single-operation latency. The shared rule and operation's contract prevent integration choosing a favorable estimator after seeing results.

## 3. General profiles admit environments; they do not adjust time

Shared profiles define reusable hardware/resource classes and observable operating conditions: architecture, effective CPU allocation, memory, relevant filesystem/storage class, runtime/build conditions and a small set of centrally implemented generic probes. Projects choose a profile; they do not build their own calibrator. Record actual resource, image and runtime metadata needed to identify the environment.

Admission checks require the declared resource conditions and fixed absolute probe ceilings before the timed operation cohort. Probes do not import product algorithms, compare the candidate with another implementation, or compute a product-time multiplier. A profile denotes an observed capability envelope, not identical processors, exclusive physical resources or a guarantee of every future latency. Missing resource metadata must be reported honestly rather than treated as proof of an allocation guarantee.

For an admitted worker, a 20 ms operation limit is **20 measured milliseconds**. The worker's speed does not alter that number. No relative error allowance, normalization, moving baseline or reference-equivalent time can satisfy this requirement.

The binding admission precedes timed operation calls. Later diagnostics cannot retroactively reject a worker and erase an observed miss. Candidate slowness itself is not an environment rejection condition. Shared checks can be amortized over a bounded cohort on one unchanged worker; they are not repeated for every member or tiny operation. Resource changes require a new applicable admission.

### Periodic shared-profile validation

Before making a profile a required gate, run a finite campaign on independently allocated workers with fixed, published probes/ceilings and representative real operation witnesses. Predeclare the campaign size, useful availability requirement, observation rules, impairment controls and limits of the claim. Validate on fresh allocations; retain every admission failure, operation miss and measurement cost. The witnesses demonstrate usefulness of a general profile, not a transferable project-time model.

Shared `all` authority sets a finite refresh cadence and invalidation conditions. Revalidate on fresh allocations over later dates and relevant image/resource changes. Do not run a multi-worker research campaign for each PR or ask every project's design author to create a new validation implementation. An ordinary per-job admission and periodic central validation have different costs and purposes.

The current v4 evidence supports the tested core cases, across four CPU models and three images in one short campaign. It does not yet establish long-term reliability. Its synchronization profile missed the availability screen, and admitted workers still had real synchronized-copy and SQLite misses. Generic direct-sync probes do not qualify every database, physical-durability or network behavior.

When a required capability lacks a dependable shared profile, record that central capability gap. Improve the operation where its guarantees allow or qualify a suitable general controlled-resource profile. Keep the affected qualification unestablished until evidence supports it. Do not hide the gap by requesting a project-specific reference implementation, widening budgets automatically, dropping slow observations, inventing a tier tuned to one failing product, or repeatedly selecting new workers until green.

### Decision and retry semantics

| Outcome | Required meaning |
| --- | --- |
| Pass | Required profile admitted; all three executions complete and correct; every raw time at or below B |
| Budget miss | Admitted profile and at least one complete raw observation above B; retain whether some or all observations missed |
| Unqualified | Required shared profile unavailable or not admitted; this supplies no performance pass |
| Invalid or failed execution | Missing/invalid evidence, incomplete work or correctness failure; this supplies no pass |

A miss establishes the observation, not its cause. Investigate code, hardware and scheduling without rewriting the result. Re-execution is diagnostic and does not erase an admitted miss or select a new fastest sample. A shared procedure may allow at most one fresh replacement for a preflight-unqualified allocation; preserve both and count the failure in availability. An aborted or incorrect execution is not a timing retry. Watchdog scaling under [#23](https://github.com/nashspence/all/issues/23) does not move a design budget.

## 4. Project-owned durability and simple cost attribution

[#35](https://github.com/nashspence/all/issues/35)'s common checkpoint machinery, 120-second target and one-eighth cost arithmetic are superseded. Each project defines its acknowledged-result guarantees, failure model, lost/replayed-work tolerance and recovery behavior, then chooses an implementation that meets those promises and the relevant normal/recovery time budgets. Required durability is included in the real operation's measured completion. Removing a common machinery prescription does not remove existing safety or acknowledged-data commitments.

Use ordinary instrumentation or existing traces when cost attribution helps a design decision. The conceptual boundaries are:

| Work category | Boundary relative to the operation |
| --- | --- |
| Input handling | Discovery, enumeration, visiting and dispatch before domain processing |
| Useful processing | Work producing the promised domain result, including required authorization and output effects |
| Optional observation | Progress/status/telemetry genuinely optional to the operation; a report that is the product's purpose is useful processing |
| Interruption protection | Work protecting this operation against its own interruption, such as checkpoints/replay tracking; restoring a backup as the product's purpose is useful processing |
| Complete operation | Everything necessary for the supported result, including coordination and promised completion |

These categories do not mandate independent executors, a layer matrix, a no-durability path or alternate reference implementations. Concerns may overlap or be inseparable; name that limitation instead of reporting an invented zero or assuming additive costs. The authoritative measurement is the complete real operation.

## 5. Early integration and large qualification outside CI

Before broad implementation depends on an architecture, demonstrate a small complete user workflow within its own raw budget; reuse a canonical CI case if it already establishes that scope. Include command startup where users invoke a command. Recheck when material coordination costs change. This is where integration must surface design pushback instead of accumulating isolated correctness results around an unusable workflow.

Before releasing a claimed scale/backend/operating profile, run its representative large end-to-end qualification **outside CI**, with a design-supplied raw wall-clock limit and applicable general profile. Use large member counts where that is the claimed capability, and relevant history, real backends, final commits/drain and interruption/recovery cases. Where no large-input dimension exists, qualify representative complete workflows or meaningful stress instead. Bind the workload to existing release semantics and record the exact revision and configuration.

Predeclare repetitions/reset conditions appropriate to an expensive campaign; every required observation must fit its budget. Do not choose a smaller campaign after a miss. Later material changes require applicable requalification. Small-unit results and simulations cannot establish unmeasured provider latency, physical durability or large-run completion. Existing native/correctness release proof is preserved.

## 6. Economical adoption and current issue surface

Implement only the small shared declaration/admission/measurement/acceptance contract through existing test and CI entrypoints. Reuse product fixtures and verification. Avoid a benchmark service, per-function inventory, mandatory profiler, alternate product implementation, repeated full research matrix or recursive tests of tests. The central runner's scope and cost must satisfy [#63](https://github.com/nashspence/all/issues/63).

Retain exact source/profile/configuration attribution, raw observations, verification, admission evidence, verdict and total measurement cost using existing evidence conventions ([#14](https://github.com/nashspence/all/issues/14), [#15](https://github.com/nashspence/all/issues/15), [#50](https://github.com/nashspence/all/issues/50)). Product time, critical path and aggregate runner work are different quantities. Local unqualified runs can retain useful functional results, but the designated acceptance path must obtain the required evidence ([#16](https://github.com/nashspence/all/issues/16), [#58](https://github.com/nashspence/all/issues/58)).

Issue direction already reconciled: **#22** and **#35** are closed `not_planned`, superseded here; **#63** retains economical nonrecursive validation while allowing adopted production budgets; **#50** points here. Relationships with **#20, #23, #34, #57, #16 and #58** retain their separate obligations. An OS label under #57 does not itself qualify performance. Earlier proposal text and experiments remain history; their matched-reference, mean/error-band and machinery recommendations are not active alternatives.

### Remaining shared adoption work

- [ ] Accept or amend this policy and implement its minimal common contract in `all`.
- [ ] Complete finite later-date/image validation of the core profile with fixed conditions and an explicit refresh/availability policy; resolve additional required resource profiles separately.
- [ ] Connect a real operation to the existing acceptance path with independently approved authority, retaining budget-miss, unqualified and correctness outcomes honestly.

The v4 prototype used a separate pinned authority checkout and rejected real candidate-manifest edits and fabricated time/budget/profile claims. It did not configure repository approval protections. Its adapter runs in the timer's process and prepares fixtures before preflight; it is not an isolation boundary against arbitrary candidate code. The implementation must match whatever trust/isolation claim it makes while retaining ordinary owning-contract review.

Consumer adoption remains separate: projects supply their numbers/profiles, map existing real operations, establish early integrated results, make their own durability/architecture decisions and complete applicable release qualifications. Publication of this issue does not merge a gate, change consumer authority, retire Riverhog #1000 or qualify Riverhog/Fishhat performance.
