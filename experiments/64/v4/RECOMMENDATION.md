# Raw wall-clock budgets on shared execution profiles

## Finding

**This is a workable direction for the tested CPU, process-start and ordinary
file operations, without project-specific reference implementations or adjusted
time. It is not yet a dependable general solution for storage synchronization
on standard public GitHub workers.**

The fresh experiment used 24 separately allocated public `ubuntu-24.04` workers,
four CPU models, three image versions, and kernels identifying AWS and Azure.
Every worker is validation: the profile probes, ceilings, operation budgets and
acceptance rule were published before this campaign. No thresholds were fitted
to these results, no successful job was rerun, and no observations were removed.

- [Original Actions run, attempt 1](https://github.com/nashspence/all/actions/runs/45692367319)
- [Frozen authority](https://github.com/nashspence/all/tree/3c88f1b3bf28b4fe5ae8973ff40412be1c049952/experiments/64/v4)
- [Candidate and workflow](https://github.com/nashspence/all/tree/ce6c39ce904c13aa8e6d5a6c619b6d2f35d47a58)
- [Predeclared plan](PLAN.md), [full results](RESULTS.md), [raw observations](observations.json),
  [recomputed analysis](analysis.json), and [analyzer](analyze.py)

There are 2,232 product timings and 1,440 generic probe timings, 3,672 in total.
The real product operation is `all_policy.protocol.check_repository`; the process
pools and process-start wrapper are experimental adapters. Copy and SQLite cases
are small resource witnesses. These are not Riverhog publication or Fishhat tests.
The budgets are predeclared demonstration values, not adopted product targets.

## The mechanism

Design attaches a raw elapsed-time maximum and a shared profile to an existing
product operation. For example, the experiment declares 20 ms for 16 serial
policy checks on `public-linux-x64-4cpu-v1`.

The common runner first checks the worker against that profile using independent,
generic probes. If admitted, it measures the actual operation three complete
times. Acceptance is simply:

```
required profile admitted
AND every result is complete and correct
AND t1 <= B AND t2 <= B AND t3 <= B
```

All times are the measured raw elapsed times. There is no candidate/reference
ratio, reference-time anchor, worker multiplier, relative-error band, normalized
millisecond, or automatic adjustment of B. Faster hardware leaves more headroom;
it does not tighten the budget. A slower admitted worker still receives exactly
the same number of real milliseconds.

This measures conformance to the chosen maximum in three observed executions.
It does not establish a mathematical worst case, a percentile, or a guarantee
for every future execution. A budget miss is an actual observation; its cause
can still be implementation, hardware, scheduling, or a combination.

### Shared profiles, not a project calibration implementation

The central profile requires Linux x64, four logical CPUs with four-CPU affinity,
at least 14 GiB reported memory, sufficient scratch space and a non-memory
filesystem. The fixed central probe runtime is Python 3.11.9. All three
observations of each generic probe must meet its fixed ceiling:

| Probe | Raw ceiling |
| --- | ---: |
| Fixed integer computation, serial | 350 ms |
| Same fixed work in four processes, including pool lifetime | 300 ms |
| SHA-256 over 256 one-MiB blocks | 250 ms |
| 256 enumeration/stat/read traversals of 16 four-KiB warm files | 150 ms |

The experimental synchronization profile adds 64 four-KiB writes to a fresh
file, each followed by `fdatasync`, within 250 ms. It measures the native API;
it does not promise physical power-loss durability or bound every database
access pattern.

These probes define a broad minimum capability envelope and screen grossly
unsuitable allocations. They do not assert equal hardware or predict the
candidate's duration. CPU model is recorded, never selected by name. Available
quota fields were null; reported allocation is not proof of physical isolation.
Memory capacity was checked, not memory-bandwidth performance. Networking and
accelerators were not qualified.

The binding preflight admission precedes timed product calls. Later probes are
diagnostic and cannot erase a product miss. No candidate timing determines
whether its worker qualifies.

## Fresh results

All 24 workers admitted the core profile. All 24 failed admission under eight
actual competing CPU processes, while retaining four-CPU affinity. All 24 also
failed when affinity was actually restricted to one CPU. These controls show
sensitivity to the tested impairments; they do not establish detection of all
possible interference.

| Complete operation | Fixed B | Observed raw range | Workers passing all three observations |
| --- | ---: | ---: | ---: |
| 16 policy checks, serial | 20 ms | 6.14–10.50 ms | 24/24 |
| 16 checks, two processes | 30 ms | 8.74–19.50 ms | 24/24 |
| 16 checks, four processes | 30 ms | 9.78–19.57 ms | 24/24 |
| 512 checks, serial | 500 ms | 197.13–314.54 ms | 24/24 |
| 512 checks, two processes | 350 ms | 138.54–246.90 ms | 24/24 |
| 512 checks, four processes | 300 ms | 118.96–215.92 ms | 24/24 |
| Complete 48-check cycle | 50 ms | 18.89–29.59 ms | 24/24 |
| Fresh interpreter checking 16 fixtures | 125 ms | 31.94–46.15 ms | 24/24 |
| Copy 16 four-KiB files and close outputs | 20 ms | 0.29–0.92 ms | 24/24 |
| Copy with file and destination-directory synchronization | 100 ms | 3.68–710.58 ms | 21/22 admitted; 2 unqualified |
| New SQLite DELETE/FULL database, 64 individual commits, close | 150 ms | 28.79–1,319.00 ms | 16/22 admitted; 2 unqualified |

Ranges include all 72 observations of each unchanged operation, including
nonadmitted workers. A 512-check traversal is its own complete operation, not a
measurement of cold 16-member latency. Tiny parallel operations were slower than
serial in these wrappers; their separate limits do not claim a speedup.

Nine of eleven operation/profile pairs passed the entire predeclared usefulness
screen: sufficient worker availability, every admitted unchanged observation
within B, and all required controls behaving as declared.

Every deliberately over-budget wait was blocked on every admitted worker. Adding
50% more actual processing often remained within B and legitimately passed.
That is what an absolute budget means: an in-budget slowdown is not automatically
a design violation. The experiment does not claim near-boundary sensitivity or
guaranteed detection of a percentage regression.

### Why fastest-of-three is the wrong acceptance rule here

One case inserted a 36 ms delay into only the middle execution of the 20 ms
serial operation. All 24 workers failed strict acceptance, while fastest-of-three
would have passed all 24. A separate complete-cycle witness exposed a 64 ms
periodic cost on every worker as well.

Fastest-of-three would also have passed all 22 admitted workers for both storage
operations, concealing one copy cohort and six SQLite cohorts with real budget
misses. Three observations do not expose every possible rare delay, but rejecting
observed violations is consistent with a maximum-style contract. Averaging or
minimum selection can answer other questions; they do not establish that these
observed executions met this maximum.

### Storage is a substantive limit

The sync profile admitted only 22/24 workers, missing the predeclared 23/24
availability screen. It also failed to make the tested storage operations
dependable at their fixed budgets.

The most revealing example is worker 18: its generic synchronization probes took
approximately 12–15 ms before the cohort and 10–11 ms afterward, yet one SQLite
operation took 976 ms. Four SQLite-miss workers (1, 3, 10, 18) passed both the
preflight and postflight synchronization checks. A later generic check would not
explain those misses away. Conversely, workers 2 and 23 failed preflight but had
all their measured storage operations within budget; they remain unqualified.

This prevents a claim that one quick storage probe guarantees bounded latency
throughout a heterogeneous hosted job. The correct consequences are to retain
the actual misses, improve the product's sensitivity to expensive commits where
its guarantees allow, or qualify a more controlled storage profile. None of
those is accomplished by raising B, relabeling time, taking the fastest result,
or selecting workers after seeing product performance. This experiment does not
prove that every hosted-storage budget is impossible.

## Who owns what

| Owner | Maintained responsibility |
| --- | --- |
| Project design | Raw time limits and a shared profile for named existing operations and release scenarios; explicit approval of changes to those requirements |
| Shared `all` authority | Generic profile definitions and probes, timer, fixed acceptance rule, evidence contract and finite profile validation |
| Integration | Thin call to the real operation, existing fixtures and correctness checks, complete evidence, and implementation changes needed to meet B |
| Ordinary owning-contract review | Confirm that the tested entrypoint, workload extent and completion boundary still mean the operation specified by the product contract |

No owner supplies a competing project implementation, a reference-time anchor,
or a project-specific calibration model. Existing product semantics and fixtures
provide the workload meaning. The design decision can be a small table of
operation/profile/time entries. An integration PR cannot silently reduce the
workload, stop the timer early, edit the accepted budget or redefine the shared
profile to accept itself.

### Authority boundary actually exercised

The workflow executed central probes, timer, acceptance and budgets from a
separate checkout pinned to the authority commit. Every job really rewrote the
candidate checkout's budget file to enormous values and a weaker profile, then
reloaded the authoritative contract. The original limits remained active on
all 24 workers. An adapter returning fabricated time, budget and profile claims
also failed its actual over-budget case on all 24.

This is a concrete demonstration of source/configuration separation, not proof
of configured GitHub approval enforcement or isolation against hostile code.
The adapter is imported and its fixtures are prepared before preflight; its
timed call runs in the same Python process as the clock. Arbitrary candidate
code could in principle monkeypatch that process. A production gate must execute
its governing runner from the trusted required-check source, preserve ordinary
independent contract review, and use an external timing/process boundary if
untrusted-code isolation is part of its claim. Copying authority files into a
candidate PR does not create independent authority.

## Cost and next policy step

The median sum of timed preflight probe calls was 1.41 seconds, or 1.36 seconds
for core-only calls. Preparation and verification are additional; the current
instrumentation does not separately time the entire preflight phase. Profile
checks should be shared across a bounded cohort on one unchanged worker, not
repeated for each member or each tiny operation.

The complete research harness took a median 22.26 seconds per worker, range
20.87–31.23 seconds, excluding Actions setup/upload. It includes 93 product
executions, deliberately inserted delays and four sets of probes, including
pressure controls. That diagnostic campaign is not the proposed recurring gate.

Adopt the policy direction of **fixed raw budgets, common profile admission,
ordinary real-operation adapters and independent numeric authority**. Retire the
matched-reference recommendation completely. Keep the following implementation
work finite:

1. Validate the central core profile again on a later date/image cohort, with
   unchanged caps and explicit availability reporting before production gating.
2. Put the common runner and approved budget source under the existing required
   review/check path; demonstrate one actual project operation through it.
3. Retain storage as unresolved for these tested budgets. Qualify any proposed
   storage profile before relying on it; do not turn CPU success into a claim
   about durable commits or remote services.
4. Preserve early complete workflows, reusing a CI case where it covers that
   scope. Keep deliberately large pre-release qualifications outside CI. Each
   has its own raw wall-time requirement and applicable environment.

This same-session evidence spans several image versions but supplies no
long-term false-alarm estimate. The earlier generic data informed broad profile
ceilings; this entire fresh campaign validated them without refitting. A passing
example does not prove applicability to every repository, language or operation.

The mechanism can be shared without asking design to implement project code.
Its honest unresolved boundary is dependable storage latency on the tested
public workers. No main-branch implementation or consumer-repository change is
part of this experimental publication.

## Reproduction and provenance

Run `python experiments/64/v4/analyze.py` to validate source/fixture identities,
recompute all 96 phase admissions and 744 case decisions, and regenerate the
result files. It launches no new workers. A separate review recomputed those
decisions directly from the raw data and found agreement.

Observations are the original first-attempt job-log JSON lines, preserving exact
integer values, with job and runner IDs appended. All 24 artifact names, IDs,
digests and run/source metadata were matched. Artifact ZIP contents were not
independently downloaded. Every observation and failure remains in the retained
data. The frozen execution sources and plan are unchanged after the campaign;
the analyzer's explanatory text was clarified during review.
