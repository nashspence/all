# V1 decision: failed and not qualified

The prospective #66 v1 acceptance campaign did **not** qualify
`public-linux-x64-4cpu-prepared-ext4-v1`. Do not activate that profile as a required
Riverhog or Fishhat performance gate.

- Frozen implementation: `bea509359a6abb2f42f56ae5ef15622ed4a3d292`.
- Workflow activation: `9f81bfa4fe431a51e9ed65d2ed41cb12ded53157`.
- Actual campaign: [GitHub Actions run 45716944073](https://github.com/nashspence/all/actions/runs/45716944073).
- Population: the original twelve jobs, first attempts only, no replacements.
- Outcome: **8/12 complete successful jobs**. Eleven prepared their resources;
  nine reached the generic and real-consumer operations.

## Exact failures

| Worker | Failure | Consequence |
|---|---|---|
| 1 | One shared CLI control could not find the installed `all-policy` command on PATH | Controls failed before storage collection; no worker operation record exists |
| 7 | Serial CPU preflight 369.610468 ms and postflight 354.649000 ms exceeded the frozen 350 ms ceiling | Preflight excluded this worker; no generic or consumer operations ran |
| 12 | One 64-sync preflight observation was 930.709848 ms against the frozen 250 ms ceiling | Preflight excluded this worker; no generic or consumer operations ran |
| 4 | One paired 64-sync postflight observation was 298.178136 ms against 250 ms | The worker failed qualification despite correct passing earlier operation observations |

The 250 ms synchronization screen was deliberately stricter than the prospective
1,280 ms complete-operation screen. Its failure is a genuine v1 criterion failure,
not a code bug. Later faster probes cannot erase it. The PATH error is a separate
workflow defect and does not excuse the other three failures.

## What the completed observations establish

All **216** collected generic observations and **54** real-consumer observations
were complete and verified. Every generic observation fit its unchanged 320 or
1,280 ms screen. Both consumers' collected observations fit the separate 320 ms
engineering comparison. The two preflight-excluded workers supply no evidence
about how their real operations would have performed.

| Whole operation | Observations | Raw range |
|---|---:|---:|
| Riverhog: 16 fresh actual 4 KiB `put_bytes` publications | 27 | 11.078–25.911 ms |
| Fishhat: 16 actual new-head CAS publications, real lock per CAS | 27 | 10.535–27.067 ms |
| Generic atomic replacement of 16 files, p1 | 27 | 8.269–28.752 ms |
| Generic atomic replacement of 16 files, p2 | 27 | 7.536–229.580 ms |
| Generic atomic replacement of 16 files, p4 | 27 | 5.453–15.131 ms |
| 64 separately synchronized appends | 27 | 14.351–45.691 ms |
| SQLite DELETE/EXTRA, 64 individual commits | 27 | 52.170–149.302 ms |
| SQLite WAL/FULL, 64 individual commits | 27 | 19.993–47.622 ms |

These are complete window timings, not individual-item or percentile guarantees.
Real synchronization, publication, recurring locks and operation-owned cleanup
were retained. Actual setup plus cleanup was 1.051–3.263 seconds on the eleven
workers that prepared storage. Riverhog's separately measured startup was
2.120–3.310 seconds; fast warm storage does not establish fast cold commands,
remote upload or complete collection publication.

## Retention and interpretation

`acceptance/manifest.json` accounts for all twelve actual GitHub jobs.
`acceptance/worker-1-job.log` preserves the control failure; the other eleven
`worker-*.json` files are the exact final JSON records recovered from job logs.
The corrected artifact upload succeeded on the formal jobs. The frozen
`analyze.py` independently reports `not_qualified`; its generated output retains
the missing-data consequences for workers whose operations did not run.

The result establishes a useful working storage implementation and a **failed
v1 qualification protocol**. It does not establish that all public Actions
storage is unusable. It also does not authorize applying looser rules to these
old observations and calling them the original successful campaign.

A separately named prospective v2 may test configuration admission plus the
unchanged complete-operation limits on fresh workers. Its claim must explicitly
withdraw v1's narrow generic-probe speed guarantee, retain all probe timings, and
leave actual operation misses binding. That is a new qualification decision;
this v1 verdict remains failed.
