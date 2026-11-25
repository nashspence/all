# Actual consumer storage bindings for #66

These bindings execute unchanged source from Fishhat `f96b83dc20f059d62a4363a63c37bb0ef8c642e5` and Riverhog `be483fd6d567616d5fcd355202d61f1e682efe75`. They measure the actual storage primitive on the prepared native timing resource. They do not rerun, replace, or claim the consumers' crash, installed-owner, provider, or release qualifications.

## Minimal normal installation

Check out both complete repositories at those exact commits. Use `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97` with `python-version: '3.12.16'` and `astral-sh/setup-uv@94527f2e458b27549849d47d273a16bec83a01e9` with `version: '0.11.24'` (the uv version already pinned by Fishhat CI). Select separate absolute environment directories outside both source trees. Given shell variables `fishhat_checkout`, `riverhog_checkout`, `fishhat_venv`, `riverhog_venv`, and `python312`:

```sh
UV_PROJECT_ENVIRONMENT="$fishhat_venv" uv sync --directory "$fishhat_checkout" \
  --locked --no-default-groups --no-editable --package fishhat-owner-support \
  --no-python-downloads --python "$python312"

UV_PROJECT_ENVIRONMENT="$riverhog_venv" uv sync --directory "$riverhog_checkout" \
  --locked --no-default-groups --no-editable --package riverhog-client \
  --no-python-downloads --python "$python312"
```

This installs each actual selected workspace package and its ordinary locked dependency closure as wheels. It omits development groups, unrelated workspace packages, and native-controller qualification. Do not substitute `--all-packages`, replace normal imports with a fabricated package namespace, or combine the environments. Their pins differ, including SQLAlchemy (2.1.5 versus 2.0.51), Alembic (1.20.0 versus 1.18.5), and rpds-py (2026.9.1 versus 2026.5.1). The original lock files, including artifact hashes and platform/extra selections, remain the installation authority:

| Repository | Exact uv.lock SHA256 |
| --- | --- |
| Fishhat | `9bd952bfee4c465e1fb8cf0b8d816361ff508d3c2767078795e0a30fdfb8650d` |
| Riverhog | `16b64145aa11bfbd6d2076a7a5adc783ed7d2e000237f9c31e9977ef48815f24` |

Build isolation follows each pinned project's build metadata; retain installation logs. The adapter verifies the exact imported product-module bytes, records installed distribution versions, and uses ordinary imports. The selected source checkout and lock identities must be recorded by the workflow. Setup/build cost is retained separately from operation timing.

To reuse the existing shared parent clock, install the shared checkout at `a324c2a1c203ac2478afaac127f385f9e1e264d3` into each completed environment with `uv pip install --python "$fishhat_venv/bin/python" --no-deps "$shared_checkout"` and the corresponding Riverhog command. These locked consumer environments already supply PyYAML6.0.3 for Fishhat; Riverhog's selected closure does **not** supply PyYAML, so install exact `PyYAML==6.0.3` there for the shared package. Do not sync that environment afterward and silently remove the explicit shared addition.

## Unchanged shared runner API

The coordinator's complete invocation is:

```sh
FROZEN_SHARED_SHA="$frozen_shared_revision" sudo --preserve-env=FROZEN_SHARED_SHA \
  "$fishhat_venv/bin/python" -I -B "$experiment_checkout/experiments/66/measure_consumer.py" \
  --kind fishhat --source "$fishhat_checkout" --shared-source "$shared_checkout" \
  --context "$native_setup_json" --work "$fresh_control_directory" --output "$consumer_record_json"
```

Use the matching Riverhog environment/source and `--kind riverhog` for the other call. When invoked by an already-root controller, no additional `sudo` is needed. The workflow supplies the full frozen shared commit; the installed shared module hashes must exactly match that checkout. The coordinator validates the literal consumer commit and original dependency lock before and after measurement. Scoped `git -c safe.directory=<exact-path>` permits these read-only checks on the runner-owned checkouts without changing global Git trust.

The coordinator retains all raw observations, excluded stages, shared source identity, consumer module/dependency provenance, and verification records. A numeric usefulness miss alone returns success so it cannot discard a valid slow observation; incomplete or invalid evidence returns nonzero. Optional `--cold` adds one complete-process diagnostic without a latency gate. Adapter exceptions retain `consumer-error.json` with their original phase and traceback; passing paths keep the unchanged shared timing protocol.

Use `fishhat_adapter.py` or `riverhog_adapter.py` as the approved `Binding.adapter` and include both that adapter and `consumer_cases.py` in `Binding.approved_files`. Set the subject to the shared experiment source checkout. Before `_measure`, the trusted controller writes `work/storage-context.json` containing `root_loop_a` and `root_loop_b` from `native_storage.setup(...)`. Execute the installed common runner under the matching consumer environment's exact Python3.12.16 and actual uid/gid0. No Fishhat enrollment variable is forged, and the main-only native-controller command is not called.

`prepare` performs imports, verifies module/version pins, checks real administrative protected ancestry and distinct filesystems, and creates new private fixtures. It writes `consumer-provenance.json`. The shared worker's parent owns request timing; no consumer duration or acceptance decision is returned. Verification writes `verification-0.json` through `verification-2.json`. Preserve these small records with the common observations, startup/drain/verification stage costs, source tuple, and native resource context.

### Fishhat operation

One warm request completes **16 successful new-head CAS publications**, each in its own actual `store.locked()` context. A retained handle reflects the selected bounded storage primitive; acquiring/releasing the recurring lock is inside every timed publication. All48 heads across the three observations are unique. Initialization and retained-handle opening happen before requests. Every actual file sync, replacement, directory sync, and lock release stays inside the request. Verification checks all16 returned transitions, reopens the actual product store, and independently reads and compares the exact current-record bytes and head. It requires no pending-file residue.

### Riverhog operation

One warm request calls actual `PrimaryFiles.put_bytes()` for **16 fresh 4KiB files**, with explicit byte admission and expected SHA256, under the retained actual construction owner. The method's file sync, hard-link publication, directory sync, candidate unlink, and final directory sync are all included. Verification closes the already-quiescent handle, reopens the real storage class to reacquire its real flock, reads each retained object through `verified()`, and independently compares its bytes. It checks the exact expected names and no candidate residue. Close/reopen does not flush or finish omitted work; `PrimaryFiles.close()` only releases handles and an unused ordering lease.

Both bindings are serial. No unsupported concurrency or fabricated owner-sharing scheme is introduced. Generic storage cases supply the independently declared p1/p2/p4 resource witnesses. The prospective320ms screen per16publications is an illustrative usefulness screen, not approved consumer design authority. A correct slow consumer is a product miss, not a reason to discard or redefine an otherwise qualified resource.

## Optional complete-process diagnostic

`consumer_cases.py --kind fishhat|riverhog --authority-root ROOT_A --journal-root ROOT_B --cold` performs fresh-process imports, fixture initialization, one16publication request, output verification, and close. Its parent may report elapsed whole-process cost separately. This deliberately broader diagnostic has no invented latency gate. Without `--cold`, the standalone JSON-line protocol is available for troubleshooting, but the campaign uses the unchanged shared worker and its clock through the adapters above.

All fixture files are new owned paths under the supplied mounts and remain until the native resource owner performs bounded cleanup. The two filesystems have different device identities and separately owned images; they share the underlying host/root failure domain. This satisfies the actual storage-class construction guard without claiming independent physical survival or installed-owner admission. Neither adapter claims persistence beyond the prepared timing-resource scope or makes a release qualification decision.
