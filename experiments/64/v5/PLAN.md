# Storage profile experiment: fixed raw budgets and actual storage semantics

## Decision to resolve

Can common storage conditions on public Linux runners support useful raw time
limits while retaining the actual required synchronization calls? Is a distinct
native scratch device available? Which claims can the observed environment
support? This is a finite investigation, not a campaign repeated until green.

Current official `actions/runner-images` source configures relaxed root mount
options, including `nobarrier,data=writeback,journal_async_commit,commit=30`.
That does not establish which settings our actual workers use. This campaign
records actual mounts, topology, kernel command line and available cache/flush
metadata. Native API calls, process-crash behavior and power-loss persistence
remain different claims. Neither tmpfs nor a successful fsync call proves the
last claim. No physical power-loss qualification is performed here.

## Frozen campaign

Run 24 fresh workers: twelve `ubuntu-24.04` and twelve `ubuntu-22.04`, with pinned
Python 3.11.9 and PyYAML 6.0.3. All allocations are validation. Preserve every
observation, unavailability, error and miss. No thresholds or budgets are fitted
to this campaign; no successful job is rerun. This extends image/OS coverage;
it does not pretend that a same-day run supplies later-date reliability evidence.

Execute this plan and its source from a separate immutable authority checkout,
published before the workflow starts. The existing real `all` protocol subject
stays frozen at `03de186a044c9c6b365347485a6c4093ce831c79`. The v4 generic probes
and their core ceilings are unchanged. Preflight admission binds; postflight
cannot erase product misses. Run the nine v4 normal core operations again under
their existing raw budgets, all three observations required to pass.

Probe scope remains finite: one preflight and one diagnostic postflight, with
all five v4 probes retained. The synchronization probe is diagnostic here; it
does not admit a physical-durability claim. Metadata and core admission are
independent of observed product times.

## Storage paths and claim scopes

Measure the same declared operation independently on:

1. A disposable directory beneath `RUNNER_TEMP`: observed native-filesystem API
   timing when the actual filesystem is non-memory/non-overlay.
2. A disposable directory beneath `/dev/shm`, only if actual tmpfs and sufficient
   space are available: explicitly volatile software-path timing.
3. A disposable directory beneath `/mnt`, only when already writable and on a
   distinct device from `RUNNER_TEMP`: observed native-filesystem API timing.

Record absent, nonwritable or aliased paths. Do not create devices, remount a
filesystem, alter its safety flags, or treat two pathnames on the same device as
independent storage. Lack of a distinct scratch disk is a result, not an error
to fix by renaming the directory. No path is selected based on its timing.

The profiles measure raw API execution under observed conditions. None can
automatically qualify power-loss persistence or the time for guaranteed durable
completion. The memory profile cannot satisfy a durable-storage requirement.
Relaxed native mount options remain visible and prevent a stronger interpretation.
No reference ratio or normalization is calculated between the paths.

## Complete operations and fixed demonstration budgets

All payloads are four KiB; outputs are independently verified after timing.
Native APIs remain enabled on every path. No `NORMAL`, `OFF`, fsync interception
or mock storage is used. Three complete observations are taken for every case.

| Operation | Completion | Raw B |
| --- | --- | ---: |
| `copy16_sync` | v4's 16-file copy, each file fdatasync, destination directory fsync; legacy namespace scope retained | 100 ms |
| `atomic16_p1` | Replace 16 existing files, each temp-file fsync, rename, containing-directory fsync | 100 ms |
| `atomic16_p2` | Same 16 replacements with two threads; include pool lifetime | 100 ms |
| `atomic16_p4` | Same 16 replacements with four threads; include pool lifetime | 100 ms |
| `append64_sync` | New log, 64 individually synchronized records, directory publication and close | 150 ms |
| `sqlite64_delete_full` | v4's new SQLite database and 64 individual DELETE/FULL commits; legacy diagnostic | 150 ms |
| `sqlite64_delete_extra` | New database, 64 individual DELETE/EXTRA commits, directory publication and close | 150 ms |
| `sqlite64_wal_full` | New database, 64 individual WAL/FULL commits, explicit TRUNCATE checkpoint, directory publication and close | 150 ms |
| `sqlite64_delete_extra_batch` | Same 64 rows, one DELETE/EXTRA transaction acknowledged as a whole | 150 ms |
| `sqlite64_wal_full_batch` | Same 64 rows, one WAL/FULL transaction acknowledged as a whole, checkpoint and close | 150 ms |

These are experimental numbers, not consumer design authority. The batch cases
change the acknowledgment granularity and cannot establish 64 separate commit
latencies. Existing preinitialized atomic targets are fixtures; new output
directories, database construction, commits, closes and thread lifetimes are
inside the declared operation where applicable. Verification restores atomic
fixtures outside timing; their reset cost remains part of the whole harness.

SQLite has one connection at a time per database. Record the actual library
version. This avoids the documented multi-connection WAL-reset bug trigger;
it is not a concurrent SQLite qualification or a recommendation to deploy an
unpatched version. A later concurrent test requires a patched library.

Two controls on every available storage path: add `B + 16 ms` to every atomic
p1 observation; add `B + 16 ms` only to the middle WAL/FULL observation. Both
must block strict acceptance whenever the required profile is admitted. The
intermittent case records why minimum selection cannot establish this contract.
There is no cross-path percentage requirement or alternative implementation.

## Predeclared interpretation

Pass requires the applicable path/profile admission, correct complete output,
and all three raw times at or below the unchanged B. Preserve mixed misses,
all-over misses, unqualified paths and invalid executions separately.

An operation/profile pair passes the campaign's usefulness screen only with
at least 23/24 admitted allocations overall, at least 11/12 per OS group, every
admitted normal observation within B, and every applicable over-budget control
blocked. Also report each OS group separately; do not select the faster group
afterward and describe it as the original all-worker qualification.

A strong timing result on relaxed native storage or tmpfs is still limited to
that observed execution scope. Storage-inclusive operator acceptance requires
an environment whose configuration and independently established failure model
match the product's acknowledgment promise. The common contract must retain that
distinction, including when no such storage profile is currently qualified.

Record resource metadata, source/fixture identities, exact times, output checks,
mount/device metadata, path availability, total harness cost, job/runner IDs and
artifact metadata. Recompute classifications from retained data. Successful
workflow completion means evidence was collected, not that every budget passed.

## Primary semantic sources

- https://github.com/actions/runner-images/blob/main/images/ubuntu/scripts/build/configure-environment.sh
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.kernel.org/filesystems/tmpfs.html
- https://docs.kernel.org/admin-guide/ext4.html
- https://docs.kernel.org/block/writeback_cache_control.html
- https://man7.org/linux/man-pages/man2/fsync.2.html
- https://www.sqlite.org/pragma.html#pragma_synchronous
- https://www.sqlite.org/wal.html#the_wal_reset_bug
