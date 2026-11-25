# #64 v4: raw wall-clock budgets on centrally admitted abstract profiles

This experiment replaces the proposed matched-reference direction. There is no
project reference implementation, candidate/reference ratio, time normalization,
reference-time anchor, candidate-derived tolerance or budget scaling. Historical
experiments remain evidence, not recommended policy.

## Authority boundary being tested

Project design supplies only a named operation's raw maximum elapsed time and
one of the shared abstract profiles. The experimental numbers below demonstrate
that contract; they are **not approved product budgets**. A real design decision
must choose them from operator requirements, not automatically from today's code.

Shared `all` infrastructure owns the generic profile probes, ceilings, clock,
fixed observation rule, evidence validation and acceptance arithmetic. Integration
provides a thin adapter invoking the actual operation and checking its result
using existing correctness fixtures. It supplies no timer readings, profile
thresholds, budgets, calibration factors or alternative implementation.

The workflow runs `measure.py`, `central.py`, `accept.py` and the design contract
from a **separate pinned authority checkout**, published before the candidate
workflow is launched. The candidate adapter and actual product are loaded from
the candidate checkout. During every CI job the candidate's own budget manifest
is actually rewritten to huge budgets and a less restrictive profile. That file
cannot change the already independent authoritative contract. A second negative
case returns a fabricated elapsed time, enlarged budget and invented profile;
none may replace the trusted outer clock or approved values. The candidate file
is restored after the measurement.

This tests a concrete source boundary, not real repository approval permissions.
Adoption still requires the ordinary protected review/required-check arrangement
that lets design approve budget changes and shared authority approve profile or
harness changes. An integration PR cannot activate its own proposed authority.
Reviewing a small fixture/entrypoint/completion declaration is still necessary;
design is not asked to implement a benchmark, competing algorithm or oracle.

## Frozen shared profiles

Both profiles require Linux x64, four logical CPUs and affinity to four CPUs,
at least 14 GiB reported memory, at least 512 MiB free scratch storage, a non-tmpfs/
non-ramfs filesystem, and the centrally pinned Python 3.11.9 probe runtime.
Record CPU model, image, kernel, filesystem and available quota metadata. A null
quota probe is unknown information, not a physical allocation guarantee.

`public-linux-x64-4cpu-v1` additionally requires **every** preflight observation
of these independent fixed probes to meet the following absolute ceilings:

| Generic probe | Ceiling |
|---|---:|
|16 integer-computation tasks,160,000 iterations each, serial|350ms|
|Same fixed computation in 4 processes, full pool lifetime|300ms|
|SHA-256 over 256 ×1MiB|250ms|
|256 enumeration/stat/read traversals of 16 ×4KiB warm files|150ms|

`public-linux-x64-4cpu-sync-v1` additionally requires every observation of a
fresh file receiving 64 writes of 4 KiB, each followed by `fdatasync`, to complete
within 250 ms. Open/write/synchronize/close is timed. This measures the native API;
it does not prove physical persistence or qualify every database access pattern.

Each probe has exactly three complete observations, with verification outside
its timer. There is no minimum-only profile admission. The probe fixture and
implementation are common to all projects and import no candidate code.

The binding admission is the **preflight** decision, before candidate execution.
Postflight probes are diagnostic. Candidate-induced resource use or an ordinary
budget miss cannot retroactively invalidate preflight and erase the miss.

The profile is a broad resource/performance envelope. No CPU model is selected
or rejected by name. The fixed ceilings were chosen as experimental broad limits
informed by earlier generic probe data; the new results cannot widen them.

## Fixed raw budgets and complete work

`design_contract.json` supplies exactly these demonstration limits:

| Operation | Raw maximum | Required profile |
|---|---:|---|
|16 real policy checks, serial|20ms|core|
|16 real policy checks, 2 or4 processes|30ms each|core|
|512 real policy checks, serial|500ms|core|
|512 real policy checks, 2 processes|350ms|core|
|512 real policy checks, 4 processes|300ms|core|
|Complete cycle of 3 ×16 serial checks|50ms|core|
|Fresh interpreter wrapper checking 16 fixtures|125ms|core|
|Copy 16 files of 4 KiB to new outputs|20ms|core|
|Same copy with each file synchronized and destination directory synchronized|100ms|sync|
|New SQLite DELETE/FULL database, 64 separately committed inserts and close|150ms|sync|

The policy checks call the real `all_policy.protocol.check_repository` on 16
distinct valid fixtures. Product code remains frozen at
`03de186a044c9c6b365347485a6c4093ce831c79` solely for experimental reproducibility;
it is the only product implementation executed, never a calibration reference.
The 512 case is 32 complete traversals, not a cold 16-member latency estimate.
Parallel process pools and the process-start wrapper are experimental adapters,
not existing product modes. The file-copy and database cases are simple resource
witnesses, not Riverhog publication or Fishhat qualification.

The trusted outer timer encloses the complete adapter call, including dispatch,
startup, output production, required commits, child-process shutdown and inserted
waiting. Fixture construction and independent output verification/reset are
outside. Work extent is checked against the declared operation. The adapter may
not select a shorter private path, return before promised completion, or relabel
product-required work as fixture setup. Physical power-loss guarantees and real
network services are outside this finite experiment.

## Acceptance: genuinely raw elapsed time

Execute each case exactly three complete times. **Pass only if all three raw
durations are at or below the unchanged design budget B** on an admitted profile.
Otherwise report:

- `mixed_miss`: some observations exceeded B;
- `all_over`: all three exceeded B;
- `unqualified`: the required profile was not admitted;
- `invalid_evidence`: missing, invalid or incorrect results.

Only `pass` establishes this experiment's conformance. Mixed observations block
acceptance just as reproducible misses do. First/minimum/mean summaries remain
diagnostics; they cannot turn an over-budget observation into conformance. Three
observations are a finite empirical maximum-style check, not a mathematical
worst-case or tail-probability guarantee. A raw miss is real for that observation,
but does not by itself prove whether implementation, scheduling or hardware
caused it.

## Predeclared fresh campaign and controls

Run 24 fresh public `ubuntu-24.04` allocations in two successive twelve-worker
matrices. **All 24 are validation; there is no fitting on this campaign.** No
successful job is rerun, no worker is discarded and no threshold changes after
viewing results. Preserve all raw values, admission failures, product misses,
source identities, total harness time and original job/artifact metadata.

For every operation collect an unchanged case and a candidate-only wait case.
The deliberate wait is `B + 16 ms`, so it necessarily exceeds the raw budget even
without the underlying work. Also collect:

- 50% more actual policy processing as a diagnostic. It may legitimately pass
  when the total still fits B: an absolute budget is not a percentage-regression
  rule.
- One 36 ms wait in the middle of the serial 16 three-observation cohort. Strict
  acceptance must expose it even though minimum selection could erase it.
- A complete 48-check cycle containing one 64 ms wait in every observation.
- A serial 16 over-budget wait plus candidate-supplied false timing/budget/profile
  claims. The outside timer and pinned contract must still determine the miss.

After the binding preflight and product cases, collect normal postflight probes,
then the same generic probes under **eight actual competing CPU processes** while
keeping CPU affinity metadata unchanged. Stop and join every competitor. Finally
collect probes with actual process affinity restricted to one CPU, and restore
the original affinity. None of these later diagnostics can change earlier
product verdicts.

For each profile/operation pair, the primary usefulness screen requires:

1. At least 23/24 normal preflight admissions for that required profile.
2. Every admitted unchanged case passes all three raw observations.
3. Every admitted deliberately over-budget case blocks acceptance.
4. Every fixed-wait/periodic-cost and authority-override negative behaves as
   prescribed, without using candidate performance to reject the environment.

Report admission and product conformance separately. If a profile admits workers
but an unchanged operation misses, retain that failure: the implementation margin
or profile/budget combination is insufficient. Do not invent a multiplier or
raise B. The stress sensitivity hypothesis is rejection on at least 23/24 CPU-busy
workers; failure means the probes did not detect that chosen pressure reliably.
A loaded worker that still meets every fixed ceiling does satisfy the declared
profile. One-CPU affinity must be rejected on all 24 workers.

The scope is one finite campaign, not repeated experimentation until green.
Later-date/image validation remains a separate adoption requirement. The public
profile need not qualify every operation; unresolved storage or launch variance
can remain explicit without installing project-specific reference machinery.

## Reproduction and status

`python experiments/64/v4/measure.py N --smoke` checks local harness mechanics;
smoke records cannot qualify CI. In CI run the script from the pinned authority
checkout with `CANDIDATE_TREE` and `AUTHORITY_REVISION` supplied by the workflow.
All numeric limits and source bytes are published before the experiment runs.
Analysis and report commits do not trigger the experiment again. No production
gate, `main` merge, scheduled calibration or consumer-repository change is made.
