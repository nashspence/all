# Shared approval: prepared native storage v2

## Decision

Approve **`public-linux-x64-4cpu-prepared-ext4-v2`** for the declared small
storage-dependent CI timing scope in Riverhog and Fishhat. This is the shared
authority decision requested by the maintainer under
[all #66](https://github.com/nashspence/all/issues/66), after the prospective
campaign and independent source/evidence review. It is not a consumer's
performance, durability, architecture or release approval.

The qualified implementation is
**`5086428a29871eeb267ea7225537aa0225930bac`**. Activation into the ordinary
shared package must preserve these tested performance-module bytes and pass the
repository's normal tests and policy check. Documentation, evidence and a
refresh workflow can be added without changing that implementation. Required
consumer workflows must select an approved shared revision independently of
their candidate source and numerical contract.

## Prospective evidence

- [Frozen v2 plan](https://github.com/nashspence/all/blob/5086428a29871eeb267ea7225537aa0225930bac/experiments/66/v2/PLAN.md), published before allocation in
  [#66](https://github.com/nashspence/all/issues/66#issuecomment-7177185251).
- [Actual acceptance run 45718971162](https://github.com/nashspence/all/actions/runs/45718971162),
  activation `d25c1fa6012e03344d0a01ac7eedcc31870b0768`.
- **12/12** original, independently allocated jobs completed successfully;
  first attempts only, no replacements or sample retries.
- **288/288** generic storage observations completed, verified and satisfied
  their unchanged 320/1,280 ms screens. Both filesystem configurations,
  all raw probes, completion boundaries and owned cleanup were verified.
- **72/72** real consumer observations completed and verified under their
  actual product guards, including a common resource inspection inside the
  actual worker. The consumer timing comparison is reported separately below.
- The shared authority/completion/source and prepared-resource controls passed
  on worker 1. The frozen source and activation also passed the normal test
  matrix and repository policy workflow. Independent review and the frozen
  analyzer both confirmed the published criterion counts and scope.

The [complete raw records and original GitHub job manifest](https://github.com/nashspence/all/tree/2e7e5a1fddc80370c8804b58013ed895545e19a4/experiments/66/v2/acceptance) and
[independent analysis](https://github.com/nashspence/all/blob/2e7e5a1fddc80370c8804b58013ed895545e19a4/experiments/66/v2/acceptance/RESULTS-v2.md) retain every observation,
diagnostic, source tuple, setup/cleanup fact and outcome. The analyzer recomputes
acceptance; it does not grant approval itself.

## The approved resource and claim

This profile requires a public GitHub-hosted Ubuntu 24.04 x64 worker with four
available CPUs, at least 14 GiB effective memory, and Python 3.12.16. The shared
helper prepares two owned, fully allocated 256 MiB ext4 loop filesystems with
verified direct I/O, enabled barriers, ordered data mode and no optional ext4
synchronous batching wait. It enables and verifies barriers and the batching
setting on the actual backing root, retains the other backing options, and
restores the two changed settings during owned cleanup.

Admission means verified **configuration, custody and correct bounded probe
execution**. It does not certify a uniform CPU-speed or probe-latency envelope.
All five raw probe timings remain visible; actual operation performance is
judged by unchanged absolute wall-clock limits. No time multiplier, matched
reference, averaging, fastest-sample selection or later diagnostic can clear an
operation miss.

The twelve workers covered six observed CPU models, three runner-image versions
and AWS/Azure kernel variants. This is finite empirical usefulness evidence,
not a guarantee that every future worker or operation will always meet a budget.
Each job still requires actual resource admission and its own operation results.

The two filesystems share their underlying host/backing failure domain. This
approval does not certify physical-power-loss survival or independent physical
storage. Existing project-specific backend, failure, custody, recovery and
release evidence remains required. No Fishhat native-controller guard was
spoofed or altered; no 83-minute correctness campaign is represented as repeated
by this timing qualification.

## Actual consumer results: one retained warning

Each observation below is a complete **16-publication window**, not one item.

| Actual operation | Observations | Raw minimum | Raw maximum | Median | 320 ms engineering comparison |
|---|---:|---:|---:|---:|---|
| Riverhog: 16 fresh 4 KiB `PrimaryFiles.put_bytes` publications | 36 | 10.871 ms | 69.181 ms | 14.864 ms | 36/36 within target |
| Fishhat: 16 new-head `CheckpointStore.compare_and_swap` publications, actual lock per CAS | 36 | 9.414 ms | 605.141 ms | 13.826 ms | **34/36 within target; 2 misses retained** |

Fishhat worker 7's three raw values were **473.010732 ms, 605.141475 ms and
33.445208 ms**. The first two exceed the prospective engineering comparison.
They are not discarded because a diagnostic probe was slow, and the fastest
third observation cannot rescue them. Their cause is not established by this
experiment. Under an approved 320 ms consumer budget, this cohort would be a
consumer performance miss.

The plan separated these consumer targets from resource qualification before
allocation. Therefore the profile can be approved while the Fishhat comparison
remains a miss. Neither comparison approves a consumer numerical requirement.

Riverhog's separately recorded startup was **2.242–3.555 seconds**; Fishhat's
was **0.254–0.383 seconds**. Warm primitive timings do not qualify cold commands,
remote upload, complete collection publication, WorkflowJournal acknowledgement
or installed-owner acceptance.

## Cost and maintenance

Actual storage setup plus cleanup was **0.998–3.823 seconds per worker**, below
the prospective 60-second bound. The full research controller, including
duplicated paired pre/post probes and all generic/consumer fixtures, took
**23.521–38.396 seconds** per worker. Dependency bootstrap was separately
**6.271–12.060 seconds**. Ordinary consumer CI amortizes preparation/admission
over a bounded cohort; it does not repeat this central twelve-worker study for
every PR or every tiny file.

Activate the central weekly twelve-worker refresh with this exact qualified
source, unchanged resource screens and a final all-jobs-success requirement.
Retain failures and suspend shared approval pending a recorded review after an
incomplete/failed refresh. A changed helper, runtime, resource configuration,
probe semantic or acceptance rule requires a new profile version and prospective
qualification. Public image/kernel changes remain recorded and reviewed.

This maintenance rule does not claim instant remote revocation of an already
pinned package. Consumers must follow the active shared decision. Per-job
configuration mismatches fail admission immediately, and actual operation budget
misses remain binding.

## V1 remains failed

The [v1 decision](https://github.com/nashspence/all/blob/a17e10f6323c954dd462f4530cc24fa6c52bee89/experiments/66/v1/DECISION.md) and all its failed evidence are unchanged.
V2 withdrew the narrower probe-speed claim prospectively; it did not adjust
ceilings just above observed maxima or retroactively approve old workers.
The complete-operation screens and actual consumer work remained unchanged.
