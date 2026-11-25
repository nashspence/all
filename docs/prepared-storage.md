# Using the prepared native storage profile in CI

`public-linux-x64-4cpu-prepared-ext4-v2` is the candidate shared native filesystem configuration for raw operation timing. Prepared v1 failed its declared campaign and was not approved; v2 requires its own prospective qualification. Use the activated shared revision and its retained qualification record in [all #66](https://github.com/nashspence/all/issues/66). The implementation, preparation manifest and fast probe results do not independently approve a profile revision or a consumer design budget.

Design supplies the operation's raw maximum wall-clock number and this profile ID. Integration supplies a small, reviewed binding to the actual production operation and ordinary output checks. The shared package owns storage preparation, admission, the outer clock and the verdict. No project implements a calibration service, reference executor, benchmark normalization or durability runtime to adopt this profile.

## Resource and scope

| Property | Prepared profile |
|---|---|
| Execution | Public GitHub-hosted Ubuntu 24.04, Linux x86-64; four available CPUs and at least 14 GiB effective memory |
| Runtime | **Python 3.12.16**, including the shared probe/runner and the timed Python operation |
| Storage | Two owned 256 MiB file-backed loop filesystems, both ext4 with verified direct I/O |
| Prepared mount settings | Barriers enabled, `data=ordered`, `max_batch_time=0`, `nosuid,nodev,noatime`, and `errors=remount-ro` |
| Backing root | Its existing data mode is preserved; barriers are enabled and `max_batch_time=0` is verified and later restored |
| Protected custody | Root-owned private ancestry and an immutable 0400 `resource.json`, bound to preparation source, repository/ref, run, attempt, runner and actual device/backing identities |
| Resource probes | Three complete, correct observations each of serial CPU, parallel CPU, SHA256, warm file reads and 64 `fdatasync` calls; all raw times are retained as diagnostics, without a v2 latency-admission cap |

The common preflight probes **both** enrolled filesystems before running a candidate. Missing custody, a different measured root, changed mount/direct-I/O settings, a mismatched runtime, incomplete/invalid probe observations or wrong probe output makes admission fail. Probe durations must be three positive integer nanosecond values; their magnitude does not admit or exclude a v2 worker. Watchdogs still bound execution. V2 withdraws the fixed CPU/synchronization probe speed envelope. It never makes a product limit larger: real operation times decide the unchanged operation gates, and a slow diagnostic cannot excuse a miss. The two filesystems share a host and backing failure domain; filesystem separation is not independent physical storage.

This profile measures actual native synchronization and operation costs. It does not certify host power-loss survival, replace an existing fault/custody proof, or change either project's failure model. The older native/volatile profiles retain their Python 3.11.9 requirement and existing numeric probe caps; the reserved stronger durable profile is a separate claim. See [the common timing and authority contract](performance.md).

## Workflow-owned setup and cleanup

Prepare once for a bounded CI cohort, reuse that resource for its operation bindings, then clean up in an unconditional final step. Report preparation, preflight, startup, verification and cleanup costs separately from warm operation times. These costs are amortized over the cohort; they are not repeated for each tiny file. A warm primitive result is not a whole CLI or end-to-end result.

The trusted workflow pins three independent revisions: the installed shared package, the approved performance contract, and the candidate. Keep installations/build artifacts and control reports outside the clean candidate checkout. The workflow must choose its repository and allowed refs from reviewed configuration, not from a proposed candidate manifest.

Install the activated shared package under the exact Python 3.12.16 interpreter. The preparation and protected-storage operations run as root on the disposable worker. Preserve the actual public GitHub/runner context through `sudo`; do not invent it. Supported triggers are trusted `push`, `workflow_dispatch`, and `schedule` only on an explicitly allowlisted `refs/heads/main`. A PR candidate can be selected independently by a trusted dispatch workflow; changing the event/ref environment is not a substitute for that workflow integration.

For example, the following commands run inside that trusted root step. `PERF_PYTHON` is the absolute installed interpreter and `CONTROL` is a new report directory on responsive control storage. The repository/ref shown are literal workflow policy; Fishhat uses its own repository value.

```sh
"$PERF_PYTHON" -I -B -m all_policy.performance.prepared_storage setup \
  --repository nashspence/riverhog \
  --allowed-ref refs/heads/main \
  --worker "$GITHUB_JOB" \
  --report "$CONTROL/preparation.json" > "$CONTROL/resource-paths.json"
```

The JSON result supplies `manifest`, `root_loop_a` and `root_loop_b`. Keep them as workflow outputs; do not select a faster target after looking at measurements. Point the performance runner at `root_loop_a`. The common profile automatically admits its paired root as well.

```sh
"$PERF_PYTHON" -I -B -m all_policy performance \
  --authority /work/approved-contract \
  --approved-revision APPROVED_CONTRACT_FULL_SHA \
  --repository nashspence/riverhog \
  --subject /work/candidate \
  --storage "public-linux-x64-4cpu-prepared-ext4-v2=$ROOT_LOOP_A" \
  > "$CONTROL/performance.json"
```

Load `ROOT_LOOP_A` and `MANIFEST` from the successful setup's JSON in the trusted workflow. After the gate, run verification and cleanup even when an operation missed its budget. Preserve the gate's nonzero exit status; successful cleanup does not change it.

```sh
"$PERF_PYTHON" -I -B -m all_policy.performance.prepared_storage verify \
  --repository nashspence/riverhog --allowed-ref refs/heads/main \
  --manifest "$MANIFEST" --report "$CONTROL/postflight.json"

"$PERF_PYTHON" -I -B -m all_policy.performance.prepared_storage cleanup \
  --repository nashspence/riverhog --allowed-ref refs/heads/main \
  --manifest "$MANIFEST" --report "$CONTROL/cleanup.json"
```

Put cleanup in an `always()` step or equivalent finalizer so a failed verification cannot skip it. The helper removes only its recorded resources and restores its two backing-root options. CLI setup failures attempt bounded cleanup while retaining the original failure. When setup stopped before publishing a complete manifest, `cleanup --partial-report ORIGINAL_REPORT` supports cleanup from the original protected failed-phase report. Do not manufacture a replacement manifest.

The Python API is the same lifecycle: `setup(expected_repository, allowed_refs, worker_id, report_path)`, `verify(context, report_path)`, and `cleanup(context, report_path)`. A `PreparationError` carries the partial context for cleanup. Default phase watchdogs are 180, 60 and 120 seconds respectively; they bound failure handling and are not acceptable product latency budgets. Keep the interpreter, installed shared source and reports responsive and outside the tested mounts.

## Thin bindings to real operations

An approved warm adapter can obtain both actual storage paths without implementing an enrollment parser:

```python
from all_policy.performance import prepared_storage

def prepare(subject, work):
    resource = prepared_storage.inspect(work)
    if resource["errors"]:
        raise RuntimeError("; ".join(resource["errors"]))
    roots = resource["resource_roots"]
    # Create ordinary operation fixtures under roots["root_loop_a"] and,
    # when needed, roots["root_loop_b"], using the actual product classes.
    return roots
```

The common worker forwards the actual non-secret run context needed by this inspector. Its successful result identifies the resource; it does not approve budgets or substitute for a product's guards. Keep temporary product fixtures uniquely named and avoid changing the canonical manifest or other bindings' state.

Default collection operations use **16 real members**. Bind p1, p2 and p4 separately where the production operation supports that concurrency, with independently approved raw numbers. Equal limits make no speedup claim. A serial checkpoint authority does not acquire meaningful parallelism by bypassing its mutex; choose a real supported collection operation when evaluating a product parallelism promise.

Every observation must do new work and return only after its promised completion. Include required file/directory syncs, publication, acknowledgements, per-request locks, joins and drain. Fixture setup cannot precompute useful processing or turn new publication into a no-op. `verify` checks completed outputs; `close` cannot supply deferred useful work. All three raw observations must fit the approved number. A minimum, mean, successful later probe or rerun cannot erase a miss.

Every warm binding needs a separately approved full-process counterpart under the common contract. That counterpart exposes imports, initialization and complete process lifecycle. Preserve startup and full-process results even when the warm operation is very fast; seconds of cold startup remain relevant to an operator launching the tool repeatedly. No experimental 320 ms resource/usefulness screen automatically becomes a consumer's warm or cold design budget.

The first existing bindings illustrate small real units:

- **Riverhog:** 16 `PrimaryFiles.put_bytes` publications, including hashing, file sync, hard-link publication, both directory syncs and candidate cleanup. This is a local prepared-primary storage primitive; remote upload and `CollectionProducer.finish()` require their own early integrated and pre-release measurements.
- **Fishhat:** 16 new-head `CheckpointStore.compare_and_swap` publications, each under its actual recurring lock with unchanged administrative/path guards. This is the checkpoint-storage primitive; it does not qualify a complete `WorkflowJournal` acknowledgement or installed owner.

Use the actual pinned source/locked installation and independently checked bytes, records or head. Keep required native correctness, custody, recovery and release evidence in its existing project-owned process.

## Evidence, refresh and adoption

Archive the raw gate JSON, preparation/postflight/cleanup reports, exact source tuple, installation provenance and all failures. Ensure the artifact-upload identity can read root-created reports; retain them even when the gate fails. A `pass` is 0, product `miss` is 1, `unqualified` is 2 and incorrect/incomplete/changed-source evidence is `failed` with exit 3. Preparation success is not itself a performance pass.

After successful v2 qualification and explicit activation, central profile maintenance belongs to `nashspence/all`: a weekly cohort of 12 fresh workers uses the same frozen profile, actual generic operation cases, raw operation screens and no-retry rules. The failed v1 campaign is never reclassified as a pass. Initial v2 qualification is limited to the one new twelve-worker campaign in its prospective plan; another failure does not authorize further threshold fitting. Consumer repositories run ordinary admission and their approved operation gates, not the central research campaign. An incomplete or failed refresh suspends shared approval pending a recorded review; raw misses remain visible. A helper, runtime, probe body/validation rule, operation screen or resource-configuration change requires a new version and qualification. Public image/kernel changes remain recorded and reviewed.

That maintenance rule does not claim automatic remote revocation of an already pinned package. The shared owner publishes the disposition and consumers must follow the active approved revision. Per-job admission still rejects an observed mismatch immediately. Activate the profile through the ordinary reviewed shared-package and repository-CI change, then select consumer numbers and bindings through their existing design authority. No additional project-specific hardware approval service is required.
