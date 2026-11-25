# #64 performance experiments (not policy adoption)

## Current direction: raw wall-clock budgets and common profile admission

The [v4 recommendation](v4/RECOMMENDATION.md) and [results](v4/RESULTS.md) report
24 fresh public workers using fixed raw operation budgets and centrally owned
generic environment checks. Nine tested core operation/profile pairs passed;
the synchronization-dependent pairs remain unqualified. No project reference
implementation, normalized time or moving budget is recommended.

The [current issue proposal](https://github.com/nashspence/all/issues/64) and its
[versioned body](v4/POLICY_PROPOSAL.md) describe the authority boundary: design
supplies raw time numbers and shared profile choices; integration connects real
operations; `all` owns common admission and measurement. The experiment does not
adopt policy, merge a gate, or change Riverhog/Fishhat.

Earlier pilot and matched-reference experiments below and in v2/v3 are retained
as history. Their proposed estimators and normalization are superseded.

## Original calibration pilot (historical)
Frozen production base: 03de186a044c9c6b365347485a6c4093ce831c79. 24 separate standard ubuntu-24.04 job allocations; Python 3.11.9 and PyYAML 6.0.3; 3 verified complete observations per case. Only this branch's script/workflow change triggers the one-shot matrix. No credentials, provider calls, scheduled jobs or new default-branch gates. Existing push workflows remain intact.

Control cases: 4096 checked warm file visits/read (16 distinct 4 KiB files, 256 traversals); 256 SHA-256 operations on 1 MiB; SQLite rollback journal FULL, 64 independent commits plus schema/setup and close (logical commit API, not physical fsync proof); independent Python integer computation at p=1,2,4 (16 items, includes pool startup/shutdown). Inputs and expected results fixed; reset and verification outside SQLite control timer. No concurrent benchmark cases within a worker. Case order rotates/reverses by allocation and repeat.

Product case: actual all_policy.protocol.check_repository against 16 varied valid versions of the original checked-in workflow in 16 disposable subject directories, 32 complete traversals = 512 checks in each timed observation. Valid output verified for every invocation; a separate negative fixture must fail. At p=2/4 use an experimental outer process pool (not a product concurrency claim); includes dispatch, startup, receiving. Report batch time (512 checks), and amortized 16-member time only as a descriptive rate, NOT a separately measured cold 16-member operation. This qualifies neither the network-backed audit nor other repositories.

Predeclared analysis: require 24 successful exact-source job observations, no sample removal. Allocation IDs 1–12 fit; 13–24 held out. For each case take the median of the 12 training three-run means as fixed reference r. Compute training max |m/r-1| plus 5 percentage points as candidate e. Maximum acceptable pilot allowance 20% (deliberately a pilot choice, not adopted policy). Test all held-out observations against that allowance; report every case, raw range, CPU/storage/image/resource strata, within-cohort spreads, and both training and held-out extremes. Also report p=2/4 speedup vs p=1 for controls and product (same job). Do not discard slow workers, infer guaranteed future coverage, or extrapolate to Riverhog/Fishhat. If the CPU and storage controls differ, do not propose a single global error. Three-run means are not confidence intervals; this small pilot cannot quantify rare tails. The held-out product measurements assess reproducibility of this frozen operation, not transfer to every production workload; no enforceable calibration or new absolute budget is established automatically. 

