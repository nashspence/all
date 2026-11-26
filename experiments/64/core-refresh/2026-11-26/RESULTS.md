# Later-date frozen core-profile repeat — 2026-11-26

**PASS** under the original installed-package 12-worker screen. [Original first-attempt run](https://github.com/nashspence/all/actions/runs/45705830013); [new first-attempt run](https://github.com/nashspence/all/actions/runs/45910890189).

Core admission: 12/12. Product observations: 72/72. Native rejection controls: 12/12. Independent record-check errors: 0. Nonpassing operation/control records: 0.

| Complete operation | Unchanged budget (ms) | Observations | Min (ms) | Median (ms) | Max (ms) | Passing workers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| check_repository16_warm | 20 | 36 | 5.774044 | 8.3186 | 10.858089 | 12/12 |
| check_repository16_cold | 125 | 36 | 59.136348 | 84.967658 | 94.082929 | 12/12 |

Image versions: {"20261116.133.1":3,"20261122.23.1":9}. CPU models: {"AMD EPYC 7763 64-Core Processor":6,"AMD EPYC 9V74 80-Core Processor":2,"Intel(R) Xeon(R) 6975P-C":4}. Complete CLI median: 2596.86761 ms (excludes checkout/install/upload). Diagnostic fdatasync cap exceedances: 0. See analysis.json for raw ranges, failures and per-worker identities.

## Custody and limits

Runtime and subject remain `a324c2a1c203ac2478afaac127f385f9e1e264d3`, authority `ed6c2dd701d5a8969166872af48b9d434d6f8af3`. Original activation `b0d7b03b8e3ffe16932d7036d1df111e088c7782`; new activation `fdd5c7f7c333dfc7d5359af04f6c79045870da19`. Only trigger branch changed, verified by exact text comparison. Separate prospective first-attempt repeat; no replacement worker or retry. Main and existing experiment refs unchanged. The branch starts from current main; incidental ordinary branch-triggered test/all jobs are not campaign observations.

The observation files retain exact JSON strings from the original first-attempt job logs; provenance retains run/job/runner identities, artifact metadata and original frozen source inventory/contracts. The accompanying Node analyzer independently checks core admission and raw-operation verdicts and native rejection scope from recorded facts, comparing recorded hashes to the original frozen inventory. It is a new evidence checker, not a rerun of the original Python analyzer. Original ZIP bytes and serialized stdout/packet digests were not independently downloaded or rehashed. Reproduce: `node analyze.mjs` in this directory. No profile, probe, operation or budget changed. Later-date evidence is not an indefinite availability guarantee, new image coverage guarantee, approval of consumer limits, native persistence claim, or new periodic maintenance decision.
