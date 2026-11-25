# Frozen shared-package validation: twelve fresh Ubuntu 24.04 workers

## Purpose and frozen inputs

Validate the actual installed shared performance package and its approved real
`all_policy.check_repository` example. This is a finite implementation and timing
qualification, not a new calibration fit or a consumer durability qualification.

The complete package is frozen at
`a324c2a1c203ac2478afaac127f385f9e1e264d3`. Publish this plan, the inactive template
and the copied authority manifests together. That publication commit is the
authority revision; record its full hash in the **later activation workflow** by
substituting the template's authority placeholder. Do not attempt to insert a
commit's own hash into the plan contained by that commit.

- **Shared runtime and candidate:** `a324c2a1c203ac2478afaac127f385f9e1e264d3`. The same commit is checked
  out separately into sibling `runtime` and `subject` directories. The replacement
  revision includes the controlled-storage collector fix. The unchanged
  performance CLI and example were inspected at predecessor
  `d99e38c943ad4f5c876de63b6691a000e3d8de37`; that predecessor is not the final pin.
- **Experimental authority:** the commit containing this plan and the copied
  manifests, published before activation. Only the later workflow and observation
  records contain its actual full hash.
  Its `.all/performance/limits.json` and `bindings.json` must be byte-for-byte copies
  of `examples/performance/{limits,bindings}.json` at the frozen shared revision. The workflow
  verifies this identity and loads the approved Git objects from a third sibling
  `authority` checkout. These remain demonstration limits, not approved consumer
  requirements.
- **Workflow source:** the later activation commit, retained through
  `github.workflow_sha` and `github.sha` in every record.
- **Runtime:** Python **3.11.9**, PyYAML **6.0.3**. Install the shared package into a
  dedicated virtual environment outside the candidate. Verify that the imported
  package is outside all three source checkouts and that every installed
  performance module matches the frozen runtime checkout.

Do not change any package, adapter, fixture, budget, probe or profile in response
to this cohort. All twelve workers are validation allocations. No minimum
selection, averaging for acceptance, normalization, automatic retries or
replacement workers are allowed.

## Trigger and allocation

The inactive template is `performance-common-64.yml.template` in this directory.
Only the root publisher activates it by writing its substituted contents to
`.github/workflows/performance-common-64.yml` on
`experiment/64-runner-calibration`, using the publisher's existing checked-head
path. Preparation commits touching this directory or the authority manifests do
not trigger the campaign.

The workflow has only a push trigger, filtered to that branch and that exact
workflow path. There is no schedule, pull-request or dispatch trigger. Run attempt
one creates a twelve-member `ubuntu-24.04` matrix with `fail-fast: false`; rerun
attempts are excluded. Each job gets a fresh runner. One activation is authorized
for this plan; changing the active workflow again would be a new campaign.

Job timeout is ten minutes. The shared package retains its 300-second cohort and
30-second phase watchdogs. The experiment collector has an independent
360-second CLI watchdog and preserves partial stdout/stderr on timeout. Setup,
installation and artifact upload are outside product observations.

## Actual operations and unchanged limits

Both operations use `public-linux-x64-4cpu-native-api-v1` and an explicit directory
beneath `RUNNER_TEMP`. There is no tmpfs substitution, remount or storage tuning.
The profile records actual mount/options/topology and makes no physical
persistence claim.

| Operation | Complete timed boundary | Fixed raw maximum |
| --- | --- | ---: |
| `check_repository16_warm` | Parent request through completion of sixteen serial real repository checks; prepared fixtures and loaded worker outside timing | 20,000,000 ns |
| `check_repository16_cold` | Fresh process, fixture creation, candidate import, sixteen checks, closed result and complete foreground process lifecycle | 125,000,000 ns |

The fixture covers valid workflows, invalid permissions, invalid jobs and missing
workflows. Approved verification checks all sixteen returned outcomes. The
adapter hash is
`00a262b020ff002739f3e90cdc5867d721d10e198df45b70ed01b88ca2508729`.

Run the actual installed command once per worker:

```sh
"$RUNNER_TEMP/common-package-venv/bin/python" -I -B -m all_policy performance \
  --authority "$GITHUB_WORKSPACE/authority" \
  --approved-revision "$COMMON_AUTHORITY_SHA" \
  --repository nashspence/all \
  --subject "$GITHUB_WORKSPACE/subject" \
  --storage "public-linux-x64-4cpu-native-api-v1=$RUNNER_TEMP/common-package-storage"
```

The invocation uses neither a package CLI shortcut nor candidate imports in the
parent. `-B` is explicit because `-I` ignores environment-based bytecode settings.
The package performs source checks before and after execution. Candidate fixtures,
timings and result files remain outside the clean candidate source tree.

## Same-worker native rejection control

After the common gate, invoke the actual installed storage collector on the same
explicit native root, without allocating another worker:

```sh
"$RUNNER_TEMP/common-package-venv/bin/python" -I -B \
  -m all_policy.performance.qualify_storage \
  --root "$RUNNER_TEMP/common-package-storage" \
  --output "$GITHUB_WORKSPACE/common-output/storage-qualification.json"
```

Retain the packet, summary stdout, stderr, exit code, command and total CLI time.
The package's own fixed 300-second deadline remains unchanged and is recorded
separately. This negative-environment control has a **60-second outer watchdog**;
on expiry, send termination and allow at most two seconds for cleanup, followed
by kill and at most two more seconds. Keep any checkpointed partial packet and
mark the outer timeout explicitly. Do not re-run it.

The preceding 24-worker inventory observed relaxed native mounts. On a worker
with those same incompatible settings, the expected result is a complete
`environment_unqualified` packet and exit 2, with both `profile_approved` and
`physical_persistence_proven` false. Check the actual configuration instead of
assuming it. A changed/safe configuration, collection failure, timeout, missing
packet or different status remains an explicit outcome; none becomes a durable
pass. This exercises real installed rejection and evidence preservation. It does
not perform power-loss testing or replace separately approved controlled-native
qualification.

## Evidence and predeclared interpretation

Each worker prints exactly one `COMMON_PACKAGE_OBSERVATION ` line containing an
envelope around the unchanged CLI JSON. The envelope records worker number,
run/attempt/job/runner identity, workflow/shared/candidate/authority revisions,
runtime and installed-module identity, exact command, CLI exit code and complete
CLI wall time. The raw package result retains generic preflight observations,
all product observations, completion/output checks, admissions, fixed budgets,
excluded startup/verification/drain costs and raw verdicts.

Artifacts retain `record.json`, exact `result.stdout.json`, `result.stderr.txt`,
`command.json`, `storage-qualification.json`,
`storage-qualification.stdout.json`, `storage-qualification.stderr.txt` and
`storage-command.json`. The final single prefixed record also contains the native
control's command, status, exit, deadlines and available packet. A nonzero package
exit is recorded without preventing artifact
upload. A well-formed `miss`, `unqualified` or `failed` package result is an
experimental outcome, not a passing performance result. Workflow success only
means collection completed. Parse, setup and watchdog errors produce explicit
collection errors with available partial output; missing records remain missing.

After completion, enrich each record with the numeric GitHub job and runner IDs
from the run's attempt-one job inventory, matched by matrix job name. Require
twelve unique workers, twelve distinct allocations and one source/authority/run
tuple. Recompute profile admission and raw decisions from the frozen package,
validate module/manifest/adapter hashes, and inspect every raw observation.

To call this twelve-worker example qualification successful, all twelve workers
must admit the declared core profile and both operations must complete correctly
with every one of the **72** raw product observations at or below its unchanged
limit. Report any unqualified allocation, incomplete cohort, mixed/all-over miss,
source mismatch or collection failure explicitly; do not replace it. If admission
is lower, report results for the actual eligible workers without calling the
twelve-worker screen successful.

Separately require every applicable relaxed-mount storage control to reject that
environment completely and retain its packet, with no approval claim. Report
changed configurations and all non-applicable or failed controls separately; they
cannot repair a common-gate miss or support a persistence claim.

Report per-operation full raw ranges and individual failure IDs, profile admission,
whole CLI cost and separately excluded costs. This small same-day cohort does not
establish future-image reliability, long-term false-alarm rates, Riverhog/Fishhat
performance, storage-inclusive durable completion, or physical persistence.
