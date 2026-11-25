# Absolute performance operations

The shared runner executes approved real-operation bindings and checks raw wall
clock limits. It does not compute a reference ratio, scale a budget, discard a
slow observation, or repeat a failed cohort until one passes. The first profiles
require Python **3.11.9**, Linux x64, four available CPUs, at least 14 GiB memory,
and fixed generic resource probes. These implementations and their measured
availability must be qualified as a new shared package; earlier experimental
probe results do not automatically qualify changed code.

The candidate prepared storage v2 profile uses Python **3.12.16** and the shared setup,
protected resource custody and paired admission described in
[Prepared native storage](prepared-storage.md). It supports small CI timing
checks with actual synchronization; existing product fault/custody/release
qualification remains separate.

## Approval and source

The protected workflow selects three independent inputs: the installed shared
`nashspence-all` revision, the approved contract revision, and the candidate
revision. Run the installed shared command in isolation, for example
`python -I -m all_policy performance`; do not import its authority or timer from
the candidate checkout. A full commit ID alone does not prove approval. Required
workflow protection and independent review determine which commit is approved.

At that approved commit, `.all/performance/limits.json` contains only schema,
operation IDs, fixed `max_wall_ns` numbers and shared profile IDs. Design does not
implement a benchmark or a reference program. Separately reviewed
`.all/performance/bindings.json` names the real operation, exact completion
boundary, commands or adapter, fixture/verifier hashes and cold counterpart.
Integration may propose that binding but cannot approve its own easier boundary
or budget. A proposed candidate edit does not activate: the runner reads approved
Git objects and checks adapter/fixture/verifier hashes before and after use.

The candidate source must be clean, including untracked and ignored files. Build
artifacts and installed dependencies belong outside that source checkout. The
reviewed binding must identify the actual candidate implementation and any
installed artifact it invokes; passing a source revision does not prove that an
arbitrary externally installed binary came from that revision. Use a dedicated
runner process. The gate owns child lifecycle, including detached descendants,
and rejects incomplete foreground command execution.

The evidence records candidate revision, approved contract revision and content
hashes, the installed shared module hashes, runtime, actual mount/options/device
and block topology, all raw probes, all observations and separate excluded costs.
This is a reviewed-code measurement boundary, not a hostile-code sandbox.

## Two explicit timing boundaries

**Command:** the parent times process launch through completed foreground command
exit. A separately approved command then checks the output. Optional fixture
preparation is reported separately. The measured command must finish all work it
promises; background descendants do not make a completed command.

**Warm request:** a tiny shared wrapper loads the approved adapter. The adapter
provides `prepare(subject, work)`, `run(context, repeat)`, and
`verify(context, result, repeat) -> True`; `close(context)` is optional. The parent
times sending each request through receipt of its completed response. Child
durations, budgets and profile claims never affect acceptance. Startup,
verification and final resource teardown are reported separately. There are
exactly three observations, using repeat IDs 0, 1 and 2.

`run` must complete the whole promised unit before returning, including its
required synchronization, acknowledgements, per-request locks and joins.
`verify` must observe completed outputs, not wait for work omitted from `run`.
`close` must not supply deferred publication, flushes or useful operation work.
These are reviewed semantic requirements; a generic clock cannot infer them from
arbitrary application code. Warm verification is separate approved checking code
in the worker, not isolated native-storage qualification. Every warm binding must
name a command binding for the same semantic operation including startup and
completion costs; reviewers check that relationship.

For example, a checkpoint compare-and-swap must publish a new head on each repeat.
An already-held lock may be excluded only when the approved unit explicitly
begins inside that existing lock; a required per-request lock may not migrate
into fixture preparation. Qualify the resources that execute the operation: a
host temporary directory does not qualify a different guest's checkpoint store.

## Storage claims and outcomes

| Shared profile | What an admitted run can claim |
| --- | --- |
| `public-linux-x64-4cpu-native-api-v1` | CPU and native filesystem API latency; no persistence qualification. |
| `public-linux-x64-4cpu-native-sync-api-v1` | Native synchronization-call API latency; no automatic persistence qualification. |
| `public-linux-x64-4cpu-volatile-memory-v1` | Software-operation and synchronization-call latency on an actual tmpfs mount; no host-crash or power-loss persistence. |
| `public-linux-x64-4cpu-prepared-ext4-v2` | Candidate configuration-admitted native ext4 pair with real synchronization and verified backing/loop identities; Python3.12.16. Probe times are diagnostic; actual operation limits remain authoritative. No fixed probe speed envelope or physical-persistence certificate. |
| `linux-x64-4cpu-qualified-durable-v1` | Reserved and unqualified until shared authority adopts infrastructure-specific evidence and a qualification mechanism. |

Storage paths are explicit workflow inputs. The runner never silently substitutes
tmpfs, disables synchronization, or promotes successful `fsync` calls into a
persistence claim. Native API evidence retains actual mount options even when
those options are unsuitable for stronger durability claims. Controlled native
qualification and the project's existing native correctness/recovery prerequisites
remain separate requirements; a metadata flag cannot approve physical durability.

Preflight admits or rejects a profile; it never changes the raw limit. All
preflights finish before candidate code runs. Every one of the three correct,
complete observations must fit its unchanged limit. `pass` exits 0; `miss` exits 1
and reports mixed versus all-over observations; `unqualified` exits 2 and is not a
pass; incorrect, incomplete, changed-source or invalid evidence is `failed` and
exits 3. A minimum or average is diagnostic only. Later environment measurements
cannot waive a miss.

One invocation has at most 32 approved operations, a 300-second cohort watchdog
and 30-second phase watchdogs. These bound small CI qualification; they do not
replace separately approved large pre-release end-to-end runs on the declared
native hardware/storage profile. No scheduled workflow is installed by this
package.

## Controlled native storage qualification

Unprepared standard public-runner storage is not a qualified substitute for a project's
stronger acknowledged-storage promise. The v5 campaign observed relaxed root
mounts on all 24 workers, and generic sync probes did not predict the actual
operation misses. A volatile profile can expose software costs but cannot earn
the missing storage-inclusive qualification. Existing project failure-model
requirements remain authoritative; this package adds no universal power-loss
promise to projects that do not make one.

Shared infrastructure owns qualification of a suitable actual storage environment.
The projects' design owners still supply only their raw numbers and a profile.
Collect the common evidence on the actual target filesystem, from the trusted
installed shared package and its specified Python runtime:

```sh
python -I -B -m all_policy.performance.qualify_storage \
  --root /path/to/actual/native/storage \
  --output /path/to/new/storage-qualification.json
```

This finite collector refuses volatile filesystems, relaxed mount settings,
unknown mount identity and unreviewed loop backing. It never mounts, formats,
changes filesystem flags, or substitutes another path. On a suitable observed
configuration it runs the common preflight and eight fixed native-operation
witnesses three times, retaining all raw results and verification. The workloads
include complete atomic replacements at parallelism 1/2/4 and individually
synchronized versus batch-acknowledged transactions. Batch success does not
qualify individually acknowledged commits.

A separate parent process enforces a total deadline of at most 300 seconds,
including preparation, probes, verification and cleanup. It checkpoints valid
partial evidence as collection proceeds. A timeout or interruption retains
completed observations and the unfinished stage, reports collection failure and
does not wait indefinitely for a worker stuck in kernel I/O. Keep the output,
installed package and interpreter on responsive control storage; use a separate
healthy filesystem when investigating storage stalls. An existing output packet
is never reused or overwritten by a new invocation.

The result is an **unapproved qualification packet**, not profile enrollment or
a product acceptance result. Exit 2 retains that status even when every numeric
screen passes; exit 3 reports collection failure. Shared review must establish
the backing storage/cache contract, fresh-run/date applicability and scope before
registering an accepted profile. Applicable existing product native fault and
custody evidence remains necessary. No new physical-power-loss test is imposed
unless the project's existing failure model requires that claim.

The presently reserved durable profile therefore fails closed. A real controlled
storage target is an infrastructure prerequisite; editing a metadata boolean,
rerunning an unsuitable public worker or passing on tmpfs cannot supply it.

The versioned prepared-ext4 profile is a separate, concrete timing resource;
its approval is governed by #66's prospective campaign and enrollment record.
A branch containing this implementation is not itself approval. Its setup enables barriers on the
backing root and both loop filesystems, retains the real file/directory sync
path, and disables optional ext4 synchronous batching delay. Its protected
manifest and actual configuration are rechecked at admission, and both storage
locations must complete the same fixed probes correctly, with three positive integer raw durations each. In prepared v2 those durations are diagnostic, not latency-admission caps; custody/configuration/runtime and bounded execution still determine admission. The fixed CPU/sync probe speed envelope is withdrawn, while the actual operation limits remain unchanged. Prepared v1 failed its declared campaign and was not approved; v2 has a distinct prospective campaign and cannot retroactively approve v1. It does not activate the reserved
physical-durability claim. See the linked setup/operation recipe and the shared
enrollment record for the exact approval, evidence and refresh boundary.

## Runnable adoption example

`examples/performance/` supplies a real `all_policy.check_repository` case: sixteen
repositories with valid, permission-invalid, job-invalid and missing workflows.
Its oracle comes from the existing protocol contract, and both warm and cold
paths call the actual candidate implementation. **20 ms warm and 125 ms cold are
predeclared demonstration budgets, not approved product requirements.**

For a reviewed adoption, place the example limits and bindings at the two
`.all/performance/` paths in the authority repository and obtain the independent
approval described above. Keep the approved fixture/adapter path in the candidate.
From a protected installed shared runner with Python 3.11.9, run:

```sh
python -I -m all_policy performance \
  --authority /work/approved-contract \
  --approved-revision APPROVED_FULL_COMMIT \
  --repository nashspence/all \
  --subject /work/candidate \
  --storage public-linux-x64-4cpu-native-api-v1=/work/performance-storage
```

The example does not install a required check or select an approval commit for
you. Its executable behavior and rejection controls are in
`tests/test_performance.py`.
