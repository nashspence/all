# Consumer adoption handoff for the shared raw wall-clock policy

Status: source-backed implementation handoff, prepared 2026-11-25. This document does not amend consumer authority, run consumer CI, qualify a new storage environment, or claim a performance pass. The first operations below reuse existing product entrypoints. Project design supplies raw time limits and shared profile choices; integration connects the real operations to the common runner through ordinary reviewed fixtures and adapters.

## Source and authority snapshot

| Repository | Read source | Current relevant authority |
| --- | --- | --- |
| `nashspence/all` | [`03de186a044c9c6b365347485a6c4093ce831c79`](https://github.com/nashspence/all/tree/03de186a044c9c6b365347485a6c4093ce831c79) | [#64](https://github.com/nashspence/all/issues/64) is still a proposal; main contains protocol/audit enforcement, not a production performance gate. |
| `nashspence/riverhog` | [`be483fd6d567616d5fcd355202d61f1e682efe75`](https://github.com/nashspence/riverhog/tree/be483fd6d567616d5fcd355202d61f1e682efe75) | [#994](https://github.com/nashspence/riverhog/issues/994), [#995](https://github.com/nashspence/riverhog/issues/995) and [#1000](https://github.com/nashspence/riverhog/issues/1000) still prescribe the common checkpoint strategy and its qualification. |
| `nashspence/fishhat` | [`f96b83dc20f059d62a4363a63c37bb0ef8c642e5`](https://github.com/nashspence/fishhat/tree/f96b83dc20f059d62a4363a63c37bb0ef8c642e5) | Installed protected checkpoint storage is accepted under [#435](https://github.com/nashspence/fishhat/issues/435)/[#439](https://github.com/nashspence/fishhat/issues/439); writable owner authority/admission remain open under [#162](https://github.com/nashspence/fishhat/issues/162)/[#166](https://github.com/nashspence/fishhat/issues/166). |

Reconcile subsequent source/authority changes before implementation. A source SHA identifies the inspected implementation, not performance qualification under the new policy.

## Shared measurement and storage conditions

Use the common outer clock, independent approved budget/profile authority and three complete raw observations. Each must complete correctly within its unchanged budget. Record admission failures and misses; a later probe or faster rerun cannot erase a miss on an admitted worker.

Fixture construction and independent verification may occur outside the clock. Required production initialization, dispatch, progress, output, synchronization, final receiving/drain and resource release remain inside the declared operation boundary. A persistent handle may be prepared outside a steady-state operation only when the product normally retains that handle; a separate cold/integrated operation must include recurring opening costs. Do not move work merely to make the small unit fit.

For synchronized storage, the profile must apply to the actual filesystem/device path used by the operation. Record observed mount, filesystem and device topology, including any overlay, loop, memory or remote backing that matters to the claim. A pathname such as `/mnt` or an OS label alone does not establish a storage class. CPU-core admission cannot qualify storage latency.

The completed [v5 storage campaign](https://github.com/nashspence/all/actions/runs/45699661412), source `667318543d25ae4c8c85fe9f100622596ccbbe3d`, retained all 24 workers and 3,096 durations. Every root reported `journal_async_commit`, `nobarrier` and `data=writeback`; none supplied a writable distinct mounted device at `/mnt`. Native API patterns produced 21 admitted worker/case groups with misses, containing 27 over-budget observations. Twenty groups would be hidden by selecting the minimum. All nine core cases and all ten tmpfs patterns passed their tested windows. [RESULTS.md](RESULTS.md) retains the complete distinctions, including native patterns that passed. Raw first-attempt log observations and artifact metadata were retained; ZIP bytes were not independently downloaded/authenticated.

No controlled-native storage enrollment was established. Tmpfs may diagnose software overhead but cannot qualify persistence beyond volatile memory. Fast API return, rename or successful `fsync` timing does not establish a power-loss guarantee. Generic synchronization witnesses characterize a shared resource profile; the actual consumer operation must still pass its own budget, and existing project native failure-domain qualification remains separate. Changed shared-package code requires its own campaign; the v5 experimental results do not automatically qualify the production implementation.

The 100/150 ms storage screens were experimental windows, not consumer design limits or evidence that useful GitHub Actions budgets are impossible. Their observed misses and the mount/backing failure-guarantee question are separate findings. A new profile must retain actual raw measurements and its honest failure scope; it cannot translate emulated timings into modern native-hardware results.

### Actual failure models and the remaining infrastructure scope

Riverhog [#994](https://github.com/nashspence/riverhog/issues/994) covers process exception/death and host/OS interruption within the qualified backend's persistence guarantees, while excluding survival of destruction of the only storage device. #1000/#999 distinguish actual backend/platform crash evidence from process-only tests and successful flush/rename.

Fishhat's installed [durability rules](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/packages/fishhat-contracts/src/fishhat_contracts/contracts/durability.schema.json) require a declared failure model for each barrier and likewise exclude a local save surviving destruction of its only device. The [workflow-journal continuity rule](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/packages/fishhat-contracts/src/fishhat_contracts/contracts/workflow-journal.schema.json) covers journal/HEAD rollback while independent authority survives, not automatic whole-authority rollback/cloning detection. [The selected virtual profile](https://github.com/nashspence/fishhat/issues/138#issuecomment-6727047279) expressly limits guest-power-interruption evidence to that virtual scope. [#299](https://github.com/nashspence/fishhat/issues/299) qualified graceful guest reboot, not arbitrary OS crash or physical power cut.

The shared policy must qualify those actual scopes without inventing a universal physical-power-loss requirement or weakening existing promises for a faster benchmark. Shared infrastructure owns the actual target, backing/cache and failure-scope evidence, finite common qualification campaign and independently approved versioned enrollment. Integration cannot activate its own enrollment or change its capability through a metadata flag. No shared controlled-storage latency enrollment is currently approved, but a reproducible disposable guest is already accessible through Fishhat's public-runner workflow. Investigate that facility before declaring external hardware unavailable or necessary. Its existing configuration is 2 vCPUs/2 GiB under TCG, not the current 4-CPU/14-GiB shared profile; add an approved common measurement stage within its actual lifetime and retain the narrow virtual scope. [qemu_profile_feasibility.md](qemu_profile_feasibility.md) identifies the exact source, hook, observed setup costs and limitations. The existing guest does not automatically qualify stronger physical-storage or latency claims.

## Riverhog: first actual publication packet

### Operation and available implementation

Use `riverhog_client.producer.CollectionProducer.publish_inputs()` in [producer.py](https://github.com/nashspence/riverhog/blob/be483fd6d567616d5fcd355202d61f1e682efe75/packages/riverhog-client/src/riverhog_client/producer.py). This existing public producer boundary constructs `IncrementalCollectionProducer`, registers input batches, invokes actual upload work, calls `finish()` and stops the producer in `finally`.

The complete operation is a fresh collection of 16 fixed-shape tiny files, at supported upload concurrency 1, 2 and 4, with independently approved raw budgets. Preserve the ordinary product configuration: authentication, encryption, provenance, primary-state persistence, required progress and the selected actual archive backend. Reuse existing product fixtures and result checks. Do not invent a second publication implementation or qualify only a hand-selected helper.

`IncrementalCollectionProducer._upload_available()` already reads configured upload concurrency/window and invokes `upload_collection_units()` with the real API client's spawn mechanism. The adapter must use that product concurrency. Running serial publications in an adapter-created process pool does not demonstrate collection upload parallelism.

### Timed completion and verification

Include all normally attributable producer preparation, file hashing, registration, upload, required commits and finalization. `finish()` currently settles local primary recovery, freezes the member inventory, advances closing, waits for a finalized receipt, stops and joins producer activity, then drains custody. Those steps belong to the measured successful completion; a receipt before drain is a different and insufficient promise. Include cold command/runtime startup in the early user-workflow case where users invoke a command.

Verify the exact member identities and bytes, finalized archive identity, custody receipts and the supported independent reading/recovery result using existing checks. Keep input/history shape, backend, cache/reset conditions, progress configuration and result extent fixed. Source hashing or provenance preparation required by the product is not free fixture construction.

The current production methods default to `poll_seconds=2.0`; the wait loop uses a 50 ms minimum sleep. Record the actual setting. A benchmark-only change to 0.05 must not disguise a slow supported default. A different supported setting or event-driven completion is a product implementation/configuration change subject to ordinary review.

### Why the current history profiler is insufficient for storage acceptance

[canonical_history_scale.py](https://github.com/nashspence/riverhog/blob/be483fd6d567616d5fcd355202d61f1e682efe75/tests/support/qualification/canonical_history_scale.py) provides real producer/API/history code coverage but deliberately submits one member per `append_inputs((source,))` call to keep its SQLite history fixture deterministic. [publication_profile.py](https://github.com/nashspence/riverhog/blob/be483fd6d567616d5fcd355202d61f1e682efe75/tests/support/qualification/publication_profile.py) explicitly declares in-process HTTP and an in-memory ciphertext test store. These are useful diagnostics, not qualification of a real storage/provider publication budget or the actual parallel upload rail.

The first acceptance adapter must connect the existing producer to a supported actual backend whose selected shared profile covers the claim. Preparing that topology and its real receiving/verification is more involved than wrapping the existing history profiler. Until it is available, retain diagnostic observations with their narrower scope; do not substitute the in-memory store or infer provider latency. Existing real-provider authorization and qualification holds remain in force.

### Early integration and release

The 16-member publication may serve as both the small CI operation and the early integrated workflow if it includes the actual complete supported path. Demonstrate that result before further broad durability architecture depends on it. If the recurring CI case is a narrower production unit, retain one small complete collection as a separately budgeted early integration witness.

Before release, qualify a representative large collection outside CI with the design-supplied raw limit/profile, actual backend, relevant member/byte/history dimensions, final commits/drain and applicable interruption/recovery cases. Reuse retained F1/F16 correctness fixtures where appropriate, but do not treat small fixtures, simulations or a bounded unit's rate as measured large-run completion. Preserve #964/#469's still-applicable growth and release obligations.

### Authority transition

Create the replacement performance/durability handoff before retiring #1000. Explicitly supersede #994/#995's universal adaptive controller, 120-second target, one-eighth arithmetic, retention prescription and #1000's mandatory matched-arm measurements. Transfer retained obligations: acknowledged evidence, nondeterministic identities, live authority, ambiguous effects, safe custody, equivalent fault windows, actual native/backend evidence, cleanup, independent recovery and complete-lifecycle work.

Settle #991's precedence hold explicitly. Closing `all #35` does not itself change Riverhog's implementation authority. Preserve existing results and useful work; adoption is not a permission to reset a branch, discard user data, weaken archive identity or perform an unapproved real-provider campaign.

## Fishhat: first actual protected checkpoint packet

### Operation and existing qualification

Use `fishhat_owner.checkpoint_store.CheckpointStore` in [checkpoint_store.py](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/fishhat/owner-support/src/fishhat_owner/checkpoint_store.py). The smallest useful bounded operation is one successful publication of a new head under the existing exclusive `locked()` context through `compare_and_swap(expected, current)`.

Use the actual installed backend, selected protected runtime/wheels and independently enrolled authority/journal contexts. Reuse [scripts/native_linux_owner_checkpoint.py](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/scripts/native_linux_owner_checkpoint.py) and its existing enrollment/storage prerequisites. [#439's acceptance](https://github.com/nashspence/fishhat/issues/439#issuecomment-7101364407) binds the current source to [fresh-main CI 45156202495](https://github.com/nashspence/fishhat/actions/runs/45156202495). It qualifies a non-admitting installed storage prerequisite with independently observed separate authority/journal filesystems, not writable owner admission or a numerical performance budget.

This operation is serial by its authority semantics. Use one raw budget; do not manufacture p2/p4 speedup on a single protected logical journal. If a later supported product workflow processes independent owners concurrently, measure that actual workflow and its resources separately.

### Timed completion and verification

For an open/publish/close case, start before `CheckpointStore.open()` and end after leaving the lock and closing owned handles. For a legitimate long-lived handle case, time acquisition through completed publication and unlock, documenting that retained-handle scope. Any recurring open/startup cost remains in the corresponding integrated operation.

The real `compare_and_swap()` path verifies the complete existing record and expected head, writes a pending file, synchronizes that file, replaces current publication and synchronizes the containing directory before success. Include every one of those costs. Use a new head: the `current == expected` branch returns without publication and is not an equivalent performance witness. Preserve stale comparison refusal and ambiguous-publication behavior; a storage failure poisons that backend instance rather than acknowledging uncertain success.

Reuse independent existing checks for exact owner/epoch/logical-journal binding, current/previous head, persisted bytes, required synchronization ordering and resource cleanup. The actual authority storage path must be covered by the selected shared storage profile. The separate journal capture filesystem remains part of the native custody contract even when this particular operation writes only the authority record.

[tests/test_protected_checkpoint_store.py](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/tests/test_protected_checkpoint_store.py) explicitly replaces administrative ancestry and capture-domain enrollment for ordinary temporary files. It must not be used to claim installed/native qualification. No standalone executable adapter is supplied here: without the existing enrolled guest and protected installed payload it would either bypass those checks or falsely claim the installed scope. Reusing the installed facility is the appropriate bounded integration task.

### Early integration and release

The next meaningful integrated performance milestone is one accepted owner operation through the actual installed admission/journal path, after #162/#166 supply that path. It must commit exact request/plan/principal/epoch, reservations and accepted target before acknowledgement/effects. Publication microbenchmarks alone cannot establish usable owner acceptance.

[WorkflowJournal.append()](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/fishhat/owner-support/src/fishhat_owner/workflow_journal.py) currently synchronizes the journal, publishes and synchronizes its local head, then retains independent checkpoint authority before returning. A faster buffered enqueue would change this accepted-result promise. Batching can be a deliberate project design, but cannot silently move the existing acknowledged durability outside the clock.

Use 16 members only for an actual supported collection workflow; do not transform one authority transaction into an artificial list. Before release, qualify the claimed realistic operation/history extent outside CI, with the raw budget/profile, actual installed storage and the retained crash/unknown-effect/recovery witnesses. [#165](https://github.com/nashspence/fishhat/issues/165) retains storage failure-domain obligations. No power-loss proof follows from this timing exercise. [release.toml](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/release.toml) still declares reference-scaffold status, no production qualification, no native qualified release profiles and no qualified native release permission.

### Authority transition

Amend conflicting report-only timing authority when adopting the new budgets: [AGENTS.md](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/AGENTS.md), [policy/performance.toml](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/policy/performance.toml), and the relevant #137/#162/#165/#166 acceptance text. Keep ordinary test-suite runtime observations distinct from canonical production budgets.

Deliberately replace the shared machinery prescription in the installed [durability contract](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/packages/fishhat-contracts/src/fishhat_contracts/contracts/durability.schema.json) and connected implementation/tests/configuration. Preserve authoritative accepted bytes, nondeterministic evidence, unknown effects, causal durable barriers, independent continuity and positive old-executor exclusion. #162/#166 remain real implementation owners; the policy transition does not complete them.

## Remaining design inputs and central delivery

The numerical design table needs only the named existing operation, a qualified shared profile and its raw maximum duration (B1/B2/B4 only where supported). Release scenarios receive their own raw limit/profile. Integration proposes the concrete adapter/fixture mapping under ordinary owning-contract review; it does not approve its own weaker budget, extent or completion boundary.

Delivering and qualifying shared admission/timing/storage machinery belongs to `all`. A central storage capability gap is not an instruction for either project's design author to implement a calibrator, reference algorithm, mock runtime or benchmark framework. Projects may begin measuring and improving actual operations while qualification remains visibly unresolved. Missing qualification cannot earn acceptance of the affected behavior.

## Startable work and acceptance boundary

Both projects can now prepare the reviewed operation binding, raw-limit/profile table and exact real completion checks; measure available paths honestly; and improve the product's coordination, processing and safe persistence granularity. Use [the shared operation guidance](https://github.com/nashspence/all/blob/a324c2a1c203ac2478afaac127f385f9e1e264d3/docs/performance.md), keeping implementation integration and required-check installation visible rather than inferring them from a PR.

Where a profile's actual capability covers the operation, obtain its three complete budgeted observations. Where stronger storage qualification is required, retain diagnostic results but keep performance acceptance unqualified until the controlled-native enrollment applies. A pending central target does not require design to write a calibrator, alternate executor or new storage runtime. It also does not authorize accepting the affected architecture on correctness alone.

[policy_status_update.md](policy_status_update.md) contains the concise #64 readiness update, focused body amendments and a finite controlled-native enrollment dependency outline. Its publication placeholders must be replaced with actual implementation and shared-package campaign identities/results. Neither that update nor this handoff mutates consumer authority, retires #1000 or qualifies either project's release.
