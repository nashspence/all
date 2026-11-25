# #66 prospective prepared-native storage campaign

Status: prospective plan. Publish this plan and its implementation revision in [all #66](https://github.com/nashspence/all/issues/66) before launching the campaign. This is a new experiment; it does not replace or reinterpret the retained #64 results.

## Decision and bounded claim

Test whether an explicitly prepared native filesystem on ordinary public GitHub Actions workers is a useful, reproducible shared resource for raw wall-clock checks in both Riverhog and Fishhat. Use real Linux storage calls and the actual pinned consumer implementations. No emulation, tmpfs substitution, replaced product guard, synchronization stub, duration normalization, or matched reference is permitted.

Two decisions are separate:

1. **Resource qualification:** the exact prepared profile is admitted and its eight generic storage witnesses satisfy the prospective screens below on all 12 acceptance workers, with complete provenance, controls and bounded preparation cost.
2. **Consumer usefulness:** actual Riverhog and Fishhat operations execute correctly under their existing guards; report their observed times against the stated 320 ms engineering target. A product timing miss remains a product miss and does not retrospectively disqualify an otherwise successful resource profile. These targets do not approve either project's authoritative performance budgets or replace its durability/release evidence.

The claim concerns this observed host, filesystem configuration, runtime and bounded campaign. It does not establish physical-power-loss survival, independent physical failure domains, a long-run availability percentage, or a latency distribution outside the sampled windows. Existing project failure models remain unchanged.

## Fixed population and execution

- Run **two fresh Ubuntu 24.04 feasibility workers**, then **12 new Ubuntu 24.04 acceptance workers**. The feasibility workers are public plumbing/dependency checks, retained in full and excluded from qualification. Do not change the profile or numeric screens in response to their durations. Plumbing fixes must be identified in the acceptance revision and do not erase feasibility failures.
- Before launching acceptance, publish the exact common implementation, plan, workflow, profile, adapter and dependency/source revisions. The acceptance workflow must consume that frozen revision. Changes after acceptance starts require a distinct future campaign; they cannot repair this campaign's verdict.
- Use one attempt per worker. Do not replace a failed worker, retry a sample, select a minimum, discard an outlier, or substitute feasibility observations. The record must account for both feasibility jobs and all 12 acceptance jobs, including missing or failed jobs.
- Use `fail-fast: false` for the acceptance matrix. Each worker uses its own new filesystem images and fixtures. Preserve every available result even when another worker fails.
- The common authority owns admission, operation clocks, limits and verdicts. Consumer code supplies actual operation results and ordinary verification; it cannot supply or alter elapsed times or activate its own authority revision.

## Exact prepared profile

| Property | Required configuration and evidence |
|---|---|
| Host | Public GitHub-hosted Ubuntu 24.04, Linux x86-64, exactly four available logical CPUs/affinity slots, at least 14 GiB effective memory; record image version, kernel, CPU model and resource limits. |
| Runtime | Python **3.12.16**, with pinned installation and consumer dependencies; record executable, distributions and source/module identities. |
| Native storage | Two newly created **256 MiB** file-backed loop devices, each formatted as ext4 and mounted as a distinct filesystem. No tmpfs, overlay substitution or QEMU guest. |
| Loop I/O | Enable direct I/O on both loops and verify the actual kernel/loop status, backing file, device and mount identities. A requested flag without successful verification is insufficient. |
| Backing filesystem | Enable and verify **`barrier=1,max_batch_time=0`** on the actual backing root. Retain all other effective mount options and topology in evidence; do not present this as an unmodified stock runner or a bare-metal disk. |
| Prepared ext4 mounts | Use the frozen, explicitly recorded ext4 mount options, including enabled barriers and `max_batch_time=0`; verify them on both mounts before timing and after collection. No disabling of required sync calls. |
| Protected paths | Actual root-owned, private paths and ancestry accepted by Fishhat's unchanged administrative, ownership, no-symlink and separate-filesystem guards. Both consumer fixtures must live on the prepared mounts. |
| Separation | The two mounts must have different filesystem/device identities. Their shared backing host remains explicit: this proves filesystem/namespace separation, **not** separate physical failure domains. |

Record the identity and options of both prepared mounts **and** the backing filesystem. Retain the setup commands, direct-I/O status, filesystem features, device mapping, free space and relevant kernel messages. A later postflight change is a failed cohort, not a reason to repair or discard earlier samples.

The preparation changes latency policy without deleting persistence operations: Linux documents `max_batch_time=0` as disabling the optional ext4 wait to batch additional synchronous work; it does not remove `fsync`, directory synchronization or write barriers. Loop direct I/O applies to backing-file I/O and is not itself a physical-persistence certificate. See [Linux ext4 documentation](https://www.kernel.org/doc/html/v6.7/admin-guide/ext4.html) and [util-linux losetup documentation](https://www.man7.org/linux/man-pages/man8/losetup.8.html).

## Admission and clocks

Run the frozen common configuration checks and bounded generic preflight on the actual prepared storage locations before any consumer operation. Publish the preflight's exact probe bodies and limits in the same frozen authority revision. They may identify an incompatible or impaired environment; they may not use product results, scale a product budget, select a faster mount, or be rerun to obtain admission. All 12 acceptance workers must pass the same admission. A failed admission remains visible and prevents successful qualification of this campaign.

Both loop filesystems must pass that admission. Run the eight generic acceptance cases on the predetermined primary filesystem, loop A; loop B supplies Fishhat's distinct journal/capture filesystem. Do not choose between A and B after viewing timings. Record the fixed placement in the workflow and each worker's evidence.

Every acceptance case has **three complete raw observations**. The common collector uses monotonic wall-clock time around the complete operation. All three must satisfy the relevant screen; the mean and minimum cannot rescue a miss. Order and fixture reset are deterministic and frozen in the implementation. Files, transactions and CAS heads must perform new work on every observation.

Setup, fixture initialization and independent result checking may occur outside a warm operation's timer. Every synchronization, publication, required lock, acknowledgement and operation-owned drain/cleanup must remain inside its real completion boundary. For parallel atomic replacements, pool construction, all submitted work and pool shutdown are timed. Nothing necessary for an acknowledged result may be deferred to verification or close.

## Prospective generic acceptance screens

Use 4 KiB payloads. The following **eight** cases are the resource acceptance witnesses. Every row is a whole-operation limit; 320 ms over 16 publications is a 20 ms/member arithmetic allowance, not a claim that each member or its p95 is at most 20 ms.

| Generic witness | Timed completion | Maximum for each of three raw observations |
|---|---|---:|
| Atomic replacement, p1 | Replace 16 existing synchronized files, each through write, file sync, atomic publication and parent-directory sync | **320 ms** |
| Atomic replacement, p2 | The same 16 replacements with actual parallelism 2; wait for all completions and shut down the pool | **320 ms** |
| Atomic replacement, p4 | The same 16 replacements with actual parallelism 4; wait for all completions and shut down the pool | **320 ms** |
| Append, 64 acknowledgements | Persist the new name and complete 64 separately synchronized 4 KiB records | **1,280 ms** |
| SQLite DELETE/EXTRA, 64 commits | Create the real database and complete 64 individual insert/commit acknowledgements, required name/directory work and close | **1,280 ms** |
| SQLite WAL/FULL, 64 commits | The equivalent 64 individual commits, including the implemented full WAL checkpoint/drain and close | **1,280 ms** |
| SQLite DELETE/EXTRA, one batch | Commit all 64 rows as **one** transaction/acknowledgement, including required directory work and close | **320 ms** |
| SQLite WAL/FULL, one batch | The equivalent single acknowledgement, including the implemented WAL checkpoint/drain and close | **320 ms** |

The equal p1/p2/p4 limits assert no parallel speedup; report all actual timings. The individual-commit and batched cases have intentionally different acknowledgement contracts and must not substitute for one another.

These screens express the operator's intended order of magnitude—tens of milliseconds of whole-window allowance per tiny acknowledged publication—while leaving room for small setup and scheduling costs. They are resource usefulness criteria selected before this campaign's data, not measured percentiles or adopted consumer design requirements. Their justification is this intended use, not the fastest prior result.

The prior #64 experiment used stricter **100/150 ms** screens on different storage configurations. Retain those original results and verdicts unchanged. Any comparisons against those numbers in this campaign are explicitly historical diagnostics; they neither alter this campaign's frozen criteria nor excuse an earlier failure. Legacy `copy16_sync` and SQLite DELETE/FULL cases, if retained by the collector, are diagnostics rather than substitutes for the eight acceptance witnesses.

## Actual consumer witnesses

Use these exact source revisions and their real installed modules, not copies with qualification/security code removed:

- Riverhog **`be483fd6d567616d5fcd355202d61f1e682efe75`**: [`riverhog_client._prepared_primary_posix.PrimaryFiles.put_bytes`](https://github.com/nashspence/riverhog/blob/be483fd6d567616d5fcd355202d61f1e682efe75/packages/riverhog-client/src/riverhog_client/_prepared_primary_posix.py). One warm observation publishes **16 distinct new 4 KiB files** through the retained real owner. Include byte admission, hashing, file sync, publication, directory sync, candidate cleanup and its final directory sync. Verify exact bytes and product identities after reopening the real store.
- Fishhat **`f96b83dc20f059d62a4363a63c37bb0ef8c642e5`**: [`fishhat_owner.checkpoint_store.CheckpointStore.compare_and_swap`](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/fishhat/owner-support/src/fishhat_owner/checkpoint_store.py). One warm observation performs **16 successive new-head CAS publications**, each with its own real `locked()` scope. Include pending-file write/sync, anchor checks, replacement, directory sync and lock release. Use 48 distinct successive heads across the three observations; a no-op CAS is not a publication. Verify the returned chain and reopened final state. Real `CheckpointStore.initialize/open` guards must succeed without monkeypatches or claimed enrollment.

For each consumer, report all three warm observations against **320 ms per complete 16-publication request**. These are common engineering usefulness targets, not a decision approving a consumer design budget. A correct but slower operation is an observed product miss. Failed guards, incomplete acknowledgement or wrong results make that consumer witness invalid and prevent claiming that the profile has been shown usable by **both** projects, even if generic resource qualification succeeds.

Record fresh-process startup/initialization and close separately, including their full elapsed cost; there is no invented cold-start acceptance budget. A separately recorded single-CAS duration, if collected, is diagnostic and cannot replace the 16-publication witness. These narrow operations do not claim full collection publication, remote upload, WorkflowJournal acknowledgement, recovery, owner admission or release readiness.

## Cost, controls and evidence

- Measure prepared-storage **setup plus cleanup**; their combined prospective limit is **60 seconds per acceptance worker**. This covers creating/formatting/attaching/mounting the two images and removing the campaign-owned storage resources. Report dependency/bootstrap cost and total job time separately; do not hide them in the operation budget.
- Use a **180-second hard watchdog for collection**, retaining partial evidence and timeout status. A watchdog termination or incomplete cleanup cannot count as a pass. Required work is never dropped to fit a budget.
- Reuse the shared runner's meaningful authority, wrong-result, delayed-operation, mutation and process-completion controls. Identify their exact source and results at the acceptance revision. These controls need not be multiplied over every worker or every operation. An absent or ineffective control is not repaired by fast normal samples.
- Preserve original per-observation nanoseconds, case/repeat identity, all functional checks, admission decisions, setup/cleanup and bootstrap timings, source hashes, runtime/topology evidence, workflow/job identity, errors and stdout/stderr. Preserve failures alongside successes. Verification must check actual retained bytes/rows/head, not merely a success field emitted by a consumer.
- Expected normal acceptance observations: **288 generic** (12 workers × 8 cases × 3) and **72 consumer** (12 × 2 × 3). Account separately for probes, feasibility runs, cold diagnostics and any legacy diagnostics; never fill missing observations with those records.

## Decision and adoption

Resource qualification succeeds only with **12/12 complete admitted acceptance workers**, all **288** generic observations within their fixed screens, correct outputs, intact provenance/controls, and setup plus cleanup within 60 seconds on every worker. A single miss yields a failed prospective qualification campaign; report exactly which condition failed. It does not prove that all possible public-worker storage profiles are unusable.

Report consumer results separately: functional applicability to both projects, the **72** raw warm timings, and any 320 ms target misses. Resource qualification may succeed while a consumer needs optimization. If generic resource qualification fails, retain the evidence and give a concrete next disposition; do not promote tmpfs, an unmodified relaxed root, or the fastest worker as a successful substitute.

The user has authorized establishing this shared profile. Activation is an ordinary versioned change in `nashspence/all`, with explicit profile scope, this prospective evidence, repository review and the actual repository CI gates. Do not invent an unspecified additional approver or let consumer integration unilaterally rewrite the profile. Pin the activated revision in consumer bindings. The existing shared checks are the Python test matrix and `all-policy check`; any additional actual repository protection remains applicable.

Neither consumer's durability contract, existing fault/custody proofs or design-budget authority changes by this campaign. Consumer design supplies its raw numerical limits on the adopted shared profile; integration binds actual operations and preserves their required work. Requalify under a new version before changing the profile, runtime or preparation, and retain observed image/kernel changes for periodic shared review. Twelve successful workers establish the bounded evidence recorded here, not a promise of perpetual public-runner availability.
