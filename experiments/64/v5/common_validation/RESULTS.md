# Installed shared-package qualification: twelve fresh workers

**Predeclared screen: PASS.** Core admission 12/12; 72/72 product observations; 12/12 complete native rejection controls.

Run: https://github.com/nashspence/all/actions/runs/45705830013 (first attempt, Ubuntu 24.04).

## Complete raw operations

| Operation | Fixed budget ms | Observations | Raw min ms | Raw median ms | Raw max ms | Pass / miss / unqualified / failed workers |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| check_repository16_warm | 20.000000 | 36 | 4.754039 | 6.1930035 | 10.980159 | 12 / 0 / 0 / 0 |
| check_repository16_cold | 125.000000 | 36 | 58.488895 | 63.1585475 | 92.952734 | 12 / 0 / 0 / 0 |

Each observation executes sixteen real `all_policy.check_repository` calls over the approved valid/invalid/missing workflow fixtures. The frozen adapter records completion and checks all sixteen outputs. Every raw observation—not a minimum or an average—must fit its unchanged limit. Median is descriptive only. The two budgets remain experimental demonstration numbers.

Warm timing covers parent request through returned completed operation. Cold timing includes a fresh process, fixture creation, import, execution, closed result and completed foreground lifecycle. Warm startup, verification and final resource teardown are recorded separately. The underlying per-repository output values are not retained in these packets: this analysis verifies the recorded checks and immutable oracle source, not a replay of those output bodies.

## Generic preflight

| Probe | Observations | Fixed cap ms | Raw min ms | Raw max ms | Over cap | Binding for this core profile |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| cpu_serial | 36 | 350.000000 | 134.667406 | 261.768570 | 0 | yes |
| cpu_p4 | 36 | 300.000000 | 75.624289 | 135.903720 | 0 | yes |
| sha256 | 36 | 250.000000 | 127.292094 | 186.142657 | 0 | yes |
| warm_files | 36 | 150.000000 | 38.801472 | 98.200897 | 0 | yes |
| fdatasync64 | 36 | 250.000000 | 10.334505 | 532.604392 | 1 | no; diagnostic |

Admission was recomputed from the frozen profile implementation and all retained metadata/probe observations. The synchronization probe cannot grant persistence qualification; it does not bind the selected core API profile. No timing was scaled.

## Native storage rejection

The installed collector produced 12/12 complete configuration rejections. Its actual mount reasons were recomputed from retained topology. The packets and CLI exits retain `profile_approved=false` and `physical_persistence_proven=false`; they are not durable-storage passes. The incompatible roots are rejected before native witness operations run, so this control contains no native storage-operation timing qualification.

The control uses a 60-second outer watchdog, separately retaining the package's 300-second deadline and checkpoint-coordinator evidence. This live rejection check does not exercise timeout handling or prove behavior during a real storage failure.

## Cost and excluded stages

| Scope | Count | Minimum ms | Median ms | Maximum ms |
| --- | ---: | ---: | ---: | ---: |
| Complete common CLI | 12 | 1868.203632 | 1971.5803055 | 2774.892154 |
| Generic preflight | 12 | 1374.654958 | 1518.125066 | 2147.531445 |
| Native rejection CLI | 12 | 213.943092 | 214.2812005 | 315.236600 |
| Both complete CLIs | 12 | 2082.350291 | 2185.882495 | 3089.282943 |
| Warm worker startup (excluded) | 12 | 46.648851 | 49.235830 | 71.778223 |
| Warm final teardown (excluded) | 12 | 7.465422 | 9.320480 | 12.547965 |
| check_repository16_warm verification (excluded) | 36 | 0.041092 | 0.0946055 | 0.413155 |
| check_repository16_cold verification (excluded) | 36 | 15.786590 | 17.1115145 | 24.941017 |

CLI costs exclude checkout, Python setup, package installation and artifact upload. These costs do not change product acceptance budgets.

## Observed allocation scope

| CPU model | Workers |
| --- | ---: |
| AMD EPYC 7763 64-Core Processor | 1 |
| AMD EPYC 9V45 96-Core Processor | 1 |
| AMD EPYC 9V74 80-Core Processor | 1 |
| INTEL(R) XEON(R) PLATINUM 8573C | 1 |
| Intel(R) Xeon(R) 6975P-C | 8 |

| Ubuntu image version | Workers |
| --- | ---: |
| 20261116.133.1 | 5 |
| 20261116.376.1 | 4 |
| 20261122.23.1 | 3 |

| Native mount source | Workers |
| --- | ---: |
| /dev/mapper/cow-root | 8 |
| /dev/nvme0n1p1 | 2 |
| /dev/sda1 | 2 |

| SQLite library | Workers |
| --- | ---: |
| 3.45.1 | 12 |

Mount options common to all allocations: `commit=30,data=writeback,discard,errors=remount-ro,journal_async_commit,nobarrier,relatime,rw`.

## Validation, provenance and limits

Validation errors: **0**. Failure IDs: **none**.

Diagnostic probe cap exceedances: fdatasync64, worker 5, zero-based repeat 2: 532.604392 ms. A nonbinding diagnostic exceedance is retained and does not change the declared core decision.

Shared package/candidate: `a324c2a1c203ac2478afaac127f385f9e1e264d3`. Authority: `ed6c2dd701d5a8969166872af48b9d434d6f8af3`. Activation workflow: `b0d7b03b8e3ffe16932d7036d1df111e088c7782`.

The analyzer checks twelve unique job/runner allocations; run/attempt/source identities; installed module, manifest and adapter hashes; deterministically serialized raw JSON/packet digests; approved timing boundaries; every recorded output check; and independently recomputed admissions and decisions. All 12 artifact metadata entries are retained. ZIP archive bytes were not downloaded or independently hashed; the analyzed raw JSON was recovered from the original first-attempt job logs.

This campaign validates the frozen shared implementation and its real repository-check example on these allocations. It does not qualify Riverhog or Fishhat, publish a new product budget, establish future-image reliability or long-term false-alarm rates, or certify physical persistence. The controlled-native infrastructure prerequisite remains unresolved by a rejection result.

## Reproduce the pure analysis

Use Python 3.11 or newer with PyYAML. Keep the evidence and frozen shared implementation in separate checkouts; the analyzer verifies the specified shared files against their immutable hashes before importing them. It does not run probes or product operations.

```sh
git clone --branch experiment/64-runner-calibration https://github.com/nashspence/all.git evidence
git clone https://github.com/nashspence/all.git shared
git -C shared checkout --detach a324c2a1c203ac2478afaac127f385f9e1e264d3
python -m pip install 'PyYAML>=6,<7'
python evidence/experiments/64/v5/common_validation/analyze.py \
  --shared-checkout "$PWD/shared" \
  --output "$PWD/common-analysis"
```

The default observation and provenance paths are beside the analyzer in the evidence checkout. No implementation is implicitly loaded from that evidence tree.
