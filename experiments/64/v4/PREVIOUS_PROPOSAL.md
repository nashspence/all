# Historical proposal body before the raw-budget revision

Superseded by [the current proposal](POLICY_PROPOSAL.md). Retained verbatim below for the revision record; its mean/error-band and normalization options are not active recommendations.

---

# Proposed direction

**Maintainer-requested policy proposal; not yet adopted or implemented.** This revision replaces this issue's earlier relative-budget proposal. It recommends authoritative **absolute wall-clock budgets on qualified execution profiles**, small real production-operation tests in ordinary CI, and separate large end-to-end qualification before release. Durability mechanisms remain project-owned. Comparative tools and diagnostic layers help explain costs; maintaining a universal layer matrix is not a prerequisite.

Publication and issue reconciliation change the proposed direction in `all`. They do not change consumer contracts, install CI gates, retire Riverhog #1000, or qualify Fishhat or Riverhog performance. Those need explicit project follow-through.

## 1. The decision this policy must enforce

Correct output alone does not establish that a tool is usable at its intended scale. Conversely, an unreliable clock comparison does not establish an implementation regression. The shared rule must require both useful performance evidence and a qualified measurement procedure, early enough to change the design.

Each project with executable behavior must maintain a small, finite inventory of material operation families whose cost grows with input or whose responsiveness matters. Its authoritative design must specify their useful result, canonical workloads, applicable execution profile, numerical wall-clock limits, and acceptance consequences. Non-executable repositories may declare this inapplicable; no artificial workload is required.

The numbers belong to the project design, not to an incidental test timeout or the current implementation's observed speed. Derive them from intended operator use and attainable performance. Use a comparable performant tool or a minimal correct path to inform that decision where useful, and disclose semantic differences. Do not set a generous limit merely because the current implementation is slow. Changing a budget, workload, completion boundary or calibration allowance requires an explicit design revision with its rationale and before/after evidence; a benchmark update cannot quietly ratify a regression.

Once adopted, a valid budget miss is performance nonconformance and prevents acceptance of the affected behavior or architecture until corrected or deliberately redesigned. Unestablished required qualification also cannot be reported as a pass. This does not prevent the experiments and corrective changes needed to resolve it, or invalidate unrelated functional results. Passing performance cannot waive correctness, security, custody or recovery obligations.

## 2. Three scopes of evidence

These are scopes, not three new frameworks or mandatory workflow files. Reuse one maintained case wherever it genuinely establishes more than one scope.

| Scope | Required execution | Purpose and timing |
| --- | --- | --- |
| Small production operation in CI | A bounded real production operation through its relevant execution path, with authoritative wall-clock limits | Recurring acceptance and regression detection through the ordinary maintained test/CI entrypoint |
| Early integrated operation | A small complete user workflow composing the relevant operations, with its own declared limit unless already covered by the CI case | Establish acceptable composition **before broad implementation depends on the architecture**, and again when material coordination costs change |
| Large pre-release qualification | Representative end-to-end workloads under a declared qualification environment, with their own absolute limits | Required before claiming the corresponding scale, backend or operating profile ready for release; deliberately large campaigns run **outside CI** |

Prefer the smallest useful production operation in recurring CI. It must reach an independently verifiable result through the real code and configuration. A pure processing helper does not qualify an operation whose actual cost includes admission, scheduling, reporting, serialization, persistence or completion. Do not fragment the measured units until expensive coordination falls between them.

Time from the operation's declared start through all work required for its promised result and completion. Include its attributable production setup, scheduling, configured progress, required durable commits, synchronization and resource release. If an API legitimately returns before background work completes, record response latency and completion/drain time separately, with limits for the relevant promises. A fast acknowledgement must not conceal growing unfinished work.

Fixture construction, independent verification and genuinely reused service setup may sit outside the product timer where their role is explicit. Product-required work may not be renamed fixture preparation. Verify every timed result; incomplete work is not a fast sample. Include command startup in the small integrated case when the user invokes a command; distinguish cold and warm service behavior when both are supported. Track harness cost economically under [#63](https://github.com/nashspence/all/issues/63).

### Canonical CI workloads

- **Collection operations:** default to the same **16 members at parallelism 1, 2 and 4**, with separate authoritative maximum wall times `B1`, `B2`, `B4`. Fix member size/distribution, ordering where relevant, existing state/history, backend, cache/reset policy and completion semantics. Sixteen is a test extent, not a product collection limit or an implementation batch size.
- **Non-collection operations:** define one meaningful bounded operation in domain terms and its own maximum; for example a query with fixed data shape, one configuration application, or a bounded stream segment. Do not manufacture a list abstraction.
- A different extent or unavailable concurrency setting must have an explicit domain/resource reason in the design. Do not require new parallel features in inherently serial products. Where parallelism is supported, test the actual assigned resources and worker/thread settings; four CPU workers on a two-core allocation do not establish four-core scaling.
- Where faster completion or increased throughput is a declared product property, specify a numerical parallel-improvement requirement and its applicable workload range, supplementing the absolute limits. Reuse the same observations where suitable and predeclare the comparison rule with its applicable reproducibility allowance. A tiny workload may legitimately test launch/coordination cost with no speedup expectation; it cannot establish a larger-workload scaling claim. Use one appropriate bounded integration or release witness for that claim. Do not require ideal linear speedup or a second percentage gate for every parallel-capable operation.
- Add only targeted cases needed for material batch/page/compaction boundaries or distinct cost regimes. Sixteen items cannot prove growth behavior or large-collection throughput. Existing complete-work growth obligations, including [#20](https://github.com/nashspence/all/issues/20), retain their separate scope.

Run each canonical case **three complete times and use their arithmetic mean**. Preserve all three values, configuration and correctness outcomes. Predeclare cold/warm/reset conditions and run ordering; interleave concurrency comparisons when practical. Do not drop the slowest run or select the best result. Failed execution remains failed execution. Three observations are a prescribed estimator, not a tail-latency guarantee or a statistical confidence interval.

If an operation is too short to measure reliably, use a fixed, declared repetition of the complete unit within each observation, retain total and per-unit values, and preserve its intended reset semantics. Do not amortize away startup or durability work that normally recurs for the operator.

## 3. Qualify the environment before enforcing its limits

The default is **raw elapsed wall time on a qualified runner profile**, not a universal CPU-score multiplier. The policy does not assert that a GitHub label identifies identical hardware or that hosted runners are already reliable enough for a particular budget.

An execution profile identifies runner class and architecture, effective CPU/memory allocation, relevant storage/filesystem/backend, runtime/build configuration, image/version evidence, concurrency settings and cold/warm conditions. Record other resource details when they affect the claim. A suitable first pilot for these public repositories is the standard x64 GitHub-hosted `ubuntu-24.04` class with resources verified in the actual job. GitHub currently documents 4 CPUs and 16 GB RAM for that public-repository class, versus 2 CPUs and 8 GB for the corresponding private-repository class; the same OS label therefore does not define one resource profile. See [GitHub's runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners). [#57](https://github.com/nashspence/all/issues/57) selects an OS generation, not performance qualification.

### Periodic calibration

Before enabling enforcement, run a finite pilot using **frozen, versioned, representative workloads across independently allocated runners**. Characterize variation between allocations as well as between repeats. The controls must be independent of the candidate code and changed dependencies: slowing both the product and its calibrator must not hide a regression.

The project records the reference measurements, relevant workload/resource class, observations, empirical relative error allowance `e`, an advance maximum acceptable allowance, refresh cadence and invalidation conditions. Qualification uses the same mean-of-three estimator as CI acceptance. For each frozen representative production workload, compare its per-allocation mean with its fixed reference mean using `abs(observed_mean / reference_mean - 1)`. The versioned allowance `e` covers the qualified variation with declared conservative headroom and remains fixed within that profile. Its applicability to the candidate operation is an empirical assumption supported by those probes, not clock accuracy or a guarantee about all future machines. CPU-only controls cannot qualify a workload dominated by storage commits, scheduling or external services. Choose only the small set of representative controls necessary for the claim.

Refresh calibration periodically on fresh allocations and after material profile, runtime, storage or calibration changes. A small independent control around a measured cohort checks whether the current allocation is within the qualified range; it must not compete with the operation while timed. Predeclared control failures or material drift make the performance comparison unqualified. The product simply running slowly is not evidence that the environment is invalid.

If reproducibility is too poor to distinguish the performance changes the design needs to detect, that profile is unsuitable. Improve the measurement, use a more stable resource profile, or make an explicit design decision. Do not expand `e`, increase `B`, or retry indefinitely to obtain a pass. The initial pilot must demonstrate adequacy before claiming this policy is enforceable on the selected hosted class.

A project may instead adopt an explicitly documented, workload-specific normalization to reference-equivalent time if raw-profile qualification is inadequate. Its predictor must be independent, validated on representative workloads **not used to fit it**, and limited to an observed applicability range. Retain raw time, scale factor and normalized time; keep the authoritative reference budget fixed. No generic benchmark multiplier or candidate-derived baseline is implicitly authorized.

### A finite, explicit decision rule

Let `m` be the arithmetic mean of the three valid times, `B` the fixed design budget, and `0 <= e < 1` the applicable qualified relative allowance. With raw timing, use the following conservative acceptance screen under that empirical reproducibility model:

`lower = m / (1 + e)` and `upper = m / (1 - e)`.

| Result | Interpretation |
| --- | --- |
| Qualified environment and `upper <= B` | Supports performance conformance for this case |
| Qualified environment and `lower > B` | Supports a budget miss |
| Interval overlaps `B`, profile/control is invalid, or required evidence is missing | Qualification is inconclusive/unestablished; no pass is earned |

These are decision bands, not a claimed statistical confidence interval. Design with enough headroom to avoid living in the overlap band. For an explicitly normalized profile, use its independently validated estimate and error convention instead; an adapter must not mix percentage definitions.

The default confirmation allowance is **one additional three-run cohort on a fresh allocation** for a miss or inconclusive result. A first qualified conformance result needs no confirmation. Preserve both cohorts when confirmation is used. Two qualifying cohorts with the same classification confirm it; a conflict or unresolved overlap remains unestablished and needs investigation, not a best-of choice. An independently invalidated initial environment supplies no performance classification, so its one replacement may establish conformance. A qualified initial miss or valid overlap cannot be discarded because the replacement is faster. Execution and correctness failures are not timing retries. Generic watchdog scaling under [#23](https://github.com/nashspence/all/issues/23) does not move these budgets.

## 4. Durability outcomes belong to the project; layers diagnose costs

Retire [#35](https://github.com/nashspence/all/issues/35) as the proposed shared checkpoint-cost direction. Shared policy must not prescribe checkpoint machinery, 120-second recovery targets, one-eighth overhead formulas, recovery controllers or retained-generation counts across domains.

Each project instead owns its acknowledged-result guarantees, failure model, acceptable lost/replayed work, recovery behavior and implementation. It must show that its chosen design satisfies those promises within the normal-path and relevant recovery budgets. Calling work mandatory does not exempt its cost from the measured production operation. Removing a shared mechanism prescription does not remove an existing safety or acknowledged-data commitment; consumer changes need explicit design and migration decisions.

Use this **optional diagnostic decomposition** when it helps choose or repair a design. The boundaries classify work relative to the operation being measured, not by module names:

| Diagnostic boundary | Included work and meaning |
| --- | --- |
| Visit/control | Traverse the declared input extent and visit each member with no domain processing or useful output. State whether discovery/materialization and scheduling are included. This diagnoses input-handling overhead; it is not a proven lower bound or a correctness-equivalent product alternative. |
| Useful processing | Produce the operation's complete successful domain result, including required transformation, authorization and output effects. Any interruption/recovery guarantees omitted in an isolated experiment are explicitly named. A no-op is not this layer. |
| Optional observation | Add progress/status/telemetry that observes that operation and is genuinely optional to its authority. If producing a report is the product's purpose, that report belongs to useful processing. |
| Interruption protection | Add work protecting this operation against its own interruption: replay tracking, checkpoints, recovery metadata or durable completion as applicable. If restoring backups is the product's purpose, restoration is useful processing, not optional protection. |
| Complete production operation | Exercise the real supported behavior, including startup, coordination, configured observation, all promised durability and completion. This is the authoritative benchmark. Any gap from the explanatory layers remains visible. |

These are conceptual comparison boundaries, not five required executors, public unsafe modes, a mandated ordering, or a Cartesian matrix. If concerns cannot be isolated without changing semantics, measure them together and say the separate cost is unknown; do not report an inseparable cost as zero. Never disable necessary authorization or perform unsafe real effects to construct a baseline. A disposable experimental path that omits crash protection is not a supported production mode.

When a peer tool or reduced path is used, run comparable workloads back-to-back under equivalent declared conditions, verify useful outputs independently, and report any unequal guarantees or excluded costs. Such comparisons support budget rationale and diagnosis; they do not replace the complete production budget or make all repositories maintain hypothetical alternate implementations. Separate ablations need not be additive; the measured cost of a behavior depends on which other behaviors are enabled.

## 5. Large end-to-end qualification before release

The authoritative design must name the supported release scenarios, workload sizes/shapes, existing history/state, concurrency, backend, environment, completion boundary and maximum total wall times. Use genuinely large member counts for products claiming large collections; include relevant interruption/recovery scenarios and retained-state costs. Where no large-input dimension exists, qualify representative complete workflows or meaningful stress conditions instead of inventing huge member counts. Define repetition and reset requirements in advance. Expensive campaigns may use a different justified repetition plan from the three-run CI rule, but not one chosen after seeing a miss. Its calibration allowance and decision rule must apply to that estimator; a mean-of-three CI allowance does not automatically qualify a single release run.

Run these large qualifications **outside CI** before releasing the corresponding capability, with evidence tied to the candidate revision and exact configuration. A later materially relevant change requires requalification; unrelated changes may reuse evidence only under explicit applicability reasoning. Report full execution through final commits/drain, actual useful throughput, and any recovery cost. The 16-member result must not be extrapolated into a claim that this qualification passed.

Real backend/network qualification and controlled local measurement have different scopes. A simulator cannot establish unmeasured provider latency or native durability. Use authorized disposable fixtures or test facilities; this policy does not authorize production publication or repeated irreversible effects. Keep existing native/correctness release requirements intact.

## 6. Adoption, enforcement cost and issue disposition

The shared implementation should be small: validate the necessary declarations and evaluate retained measurements through existing project test adapters. Share only genuinely common executable semantics, with a few targeted negative controls for missing/invalid evidence, a valid miss and invalid calibration. Projects run their actual operations; passing a synthetic evaluator is not product qualification. No generic benchmark service, mandatory full profiler, per-function benchmark inventory, recursive metatest hierarchy or additional workflow is required.

Retain exact source/profile/configuration attribution, three raw values, aggregate, calibration version/validity, completion verification and the actual decision in existing evidence conventions ([#14](https://github.com/nashspence/all/issues/14), [#15](https://github.com/nashspence/all/issues/15), [#50](https://github.com/nashspence/all/issues/50)). Keep product wall time separate from aggregate runner work and harness cost. Apply [#63](https://github.com/nashspence/all/issues/63)'s economical, nonrecursive enforcement; it does not waive this policy's small canonical production measurement. An ordinary local suite may report a nonqualified machine as unestablished, but the designated acceptance path must obtain qualified evidence rather than convert a skip into a pass ([#16](https://github.com/nashspence/all/issues/16), [#58](https://github.com/nashspence/all/issues/58)).

Recommended issue direction:

- Close **#22** as `not_planned`, superseded here: preserve honest execution/evidence reporting; retire the blanket prohibition on authoritative timing acceptance criteria.
- Close **#35** as `not_planned`, superseded here: preserve original bodies, comments and reference work as history; return durability mechanism choices to project design. Neither closure claims implementation or consumer adoption.
- Reconcile **#63**: retain economical validation and no single universal CI-duration number, while allowing explicitly adopted project-specific production-operation budgets to govern acceptance.
- Redirect **#50**'s live performance-policy reference here; clarify relationships with **#20, #23, #34, #57, #16 and #58** without changing their distinct proof obligations.

### Shared adoption work owned by this issue

- [ ] Accept or amend this policy direction and implement its minimal executable contract in `all`.
- [ ] Complete a finite calibration pilot/example with a representative operation; publish cross-runner measurements, error allowances, applicability and refresh rules. No reliable hosted-runner calibration is claimed by this issue, and one example does not qualify every project's workload.
- [ ] Demonstrate the minimal adapter/evaluator in the ordinary test path, including a valid budget miss and missing qualification that cannot pass while functional outcomes remain truthful.

### Separate consumer adoption and release work

Each adopting project must record its authoritative operations, workloads, budgets, profiles, parallel expectations and release scenarios before expanding the affected design; qualify its actual measurements and connect them to ordinary acceptance; establish the early integrated result; reconcile conflicting existing authority and make its durability/architecture decisions; and complete applicable non-CI large end-to-end qualification before the release claim. These are consumer-owned follow-ups, not a requirement to finish every downstream release before closing this shared-policy issue.

Riverhog and Fishhat follow-up decisions are separate work. Neither the existence of Riverhog #1000 nor Fishhat's existing checkpoint helper establishes acceptable end-to-end latency, and this proposal does not prejudge the measured outcome of a replacement design.

