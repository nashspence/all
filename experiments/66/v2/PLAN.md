# #66 v2 prospective configuration-admission campaign

Publish this plan, the exact implementation/workflow revisions and the v1 outcome in [all #66](https://github.com/nashspence/all/issues/66) **before allocating the v2 workers**. This is one new, bounded experiment. It does not approve the failed v1 campaign or alter its recorded results.

## Why the claim changes

Prepared v1 finished with 8/12 successful workers. One worker stopped at a PATH/control-plumbing failure. Two failed preflight timing screens before operations ran: serial CPU 369.6 ms exceeded 350 ms, and 64 `fdatasync` calls took 930.7 ms against 250 ms. Another worker passed its real operations but failed a postflight sync screen at 298 ms. All **216 generic** and **54 consumer** observations that actually ran satisfied their existing operation screens. The missing operations remain missing; they are not presumed to pass.

The v1 plan deliberately chose the 250 ms sync admission screen to be stricter than its 1,280 ms complete append/transaction screen. That was an explicit design choice, not an implementation error. V2 changes the promise rather than rounding its caps to accommodate observed maxima:

- **Admission establishes configuration, custody and correct functioning.** Both resource roots must match the fixed profile and complete the five generic probes correctly. Their raw durations remain visible diagnostics.
- **Actual operation screens establish storage performance.** The eight complete native-operation cases keep exactly the same 320/1,280 ms limits and all-three-observations rule.

The new profile is **`public-linux-x64-4cpu-prepared-ext4-v2`**. It **withdraws the fixed CPU/synchronization probe speed envelope**. It does not widen any actual operation or product budget, normalize elapsed time, use a matched reference, or change persistence operations. A slow diagnostic cannot excuse a real operation miss. Prepared v1 is not registered as an approved replacement in the new package.

## Unchanged resource

Use public GitHub-hosted Ubuntu 24.04, Linux x86-64, exactly four available CPUs and at least 14 GiB effective memory, with **Python 3.12.16**. The shared helper prepares the same two owned **256 MiB** ext4 loop filesystems with verified direct I/O and root-owned private ancestry. Prepared mounts retain enabled barriers, `data=ordered`, `max_batch_time=0`, `nosuid,nodev,noatime` and `errors=remount-ro`. The actual backing root retains its existing data mode while barriers and `max_batch_time=0` are verified and restored during cleanup.

The provisioning, operation and synchronization command bodies are unchanged. Retain backing/device identities, effective options, source hashes and the protected canonical manifest. Different filesystem identities do not create independent physical failure domains. There is no physical-power-loss certificate or stronger universal failure-model requirement.

## Admission and bounded execution

Before candidate operations, inspect both exact filesystem roots and run the same fixed serial CPU, parallel CPU, SHA256, warm file-read and 64-`fdatasync` probes. Repeat the same inspection/probes after operations. For each probe, require exactly three **positive integer raw nanosecond durations**, completed correct outputs and no execution/metadata error. Missing/invalid observations, wrong output, mismatched runtime or custody, changed root/options/direct-I/O state and incomplete execution remain failures. Raw probe magnitude alone is not a v2 admission or rejection rule. The older native/volatile profiles keep their existing numeric caps unchanged.

The existing watchdogs remain mandatory: a maximum 180-second collection and the existing bounded operation/helper phases. Preparation plus cleanup must still complete within **60 seconds** per worker, with full cleanup demonstrated. Record dependency installation, startup, verification, cleanup and total job costs separately. No required work may be omitted or moved past acknowledged completion to meet a limit.

## Fixed performance screens

Use the same 4 KiB payloads, unchanged operation bodies and verification. Each worker produces three raw observations of each row; **every** observation must fit its limit.

| Complete generic operation | Maximum raw wall time |
|---|---:|
| 16 atomic replacements at p1 | 320 ms |
| 16 atomic replacements at p2, including pool completion/shutdown | 320 ms |
| 16 atomic replacements at p4, including pool completion/shutdown | 320 ms |
| 64 separately acknowledged synchronized appends | 1,280 ms |
| SQLite DELETE/EXTRA, 64 individual commits | 1,280 ms |
| SQLite WAL/FULL, 64 individual commits including checkpoint/drain | 1,280 ms |
| SQLite DELETE/EXTRA, one 64-row transaction/acknowledgement | 320 ms |
| SQLite WAL/FULL, one 64-row transaction/acknowledgement including checkpoint/drain | 320 ms |

Run all eight cases on predetermined loop A; qualify loop B as the paired resource. Use three independent fresh fixtures per case and the unchanged fixed rotated order, parent-owned monotonic clocks and separately checked actual outputs. Do not select a faster root. Equal p1/p2/p4 limits make no speedup claim. Batch acknowledgement cannot substitute for individual acknowledgements. A 320 ms window for 16 publications is an arithmetic allowance, not a per-item percentile guarantee.

The actual consumer witnesses also remain unchanged:

- Riverhog source **`be483fd6d567616d5fcd355202d61f1e682efe75`**: 16 new `PrimaryFiles.put_bytes` publications through the actual installed implementation, including hashing, syncs, publication and candidate cleanup.
- Fishhat source **`f96b83dc20f059d62a4363a63c37bb0ef8c642e5`**: 16 successive new `CheckpointStore` CAS heads, each with its actual recurring exclusive lock and all guards/syncs intact.

Preserve locked installations and output verification. Report each consumer's three warm observations against the existing **320 ms engineering usefulness target**, separately from resource qualification. A correct slow consumer remains a product miss rather than invalidating the resource. Correct real execution is required to establish applicability to both projects. Keep full-process/startup costs visible; they have no invented new budget and are not included in a claim about warm primitive latency. No consumer design budget, recovery/custody proof, upload completion or release requirement is approved by these witnesses.

## Exactly one fresh campaign

Allocate **12 fresh acceptance workers once**, with first attempts only and `fail-fast: false`. No new feasibility sample is counted, no v1 worker is reused, and no failed worker/sample is replaced. Publish the exact frozen v2 source and activation workflow before allocation. Correct the PATH/isolated-environment wiring that prevented the v1 control step from running; retain the existing assertions and authority/completion controls. Run those controls once, on worker 1. Retain raw artifacts with readable ownership and embed the raw pre/post evidence in each worker's record.

Expected observations are **288 generic** and **72 consumer**, plus the separately identified probes and cold diagnostics. Preserve every raw duration, verification, source/runtime/resource identity, stage cost, exception, timeout, missing worker and command conclusion. Means/minima are diagnostic only. No rerun, postflight reclassification, discarded outlier or timing-cap adjustment may repair this campaign.

Resource qualification requires **12/12** complete admitted workers, all 288 generic observations correct and within their unchanged screens, valid source/control evidence, unchanged resource configuration and setup-plus-cleanup within 60 seconds on every worker. Report the 72 consumer observations and their usefulness verdicts separately, including any missing or incorrect execution.

**Stop rule:** if this one v2 campaign fails, report that this investigation has not established a qualifying public-CI storage profile for both projects. Do not fit another threshold or silently launch another qualification attempt. This is a bounded investigation outcome, not a claim that every possible GitHub Actions configuration is impossible.

Only a successful campaign and the ordinary recorded shared review/CI process can activate v2. Weekly central refresh remains unactivated until then. Successful activation does not alter existing project durability promises; consumers still select their own authoritative raw budgets and bind actual operations through the shared machinery.
