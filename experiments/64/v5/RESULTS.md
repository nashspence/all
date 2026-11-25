# V5 storage profile results

Raw API timing only; no physical power-loss or guaranteed durable-completion qualification.

Source: `667318543d25ae4c8c85fe9f100622596ccbbe3d`. Authority: `6eb72376af796f132461be9deded28829adead67`.

Run: https://github.com/nashspence/all/actions/runs/45699661412

Records retained: **24/24**. Distinct jobs: **24**. Distinct runners: **24**. Evidence integrity: **pass**.

Exact duration count: **3,096** = 648 core + 1,728 storage + 720 generic-probe observations. The declared available-path extent requires 3,096.

The initial workflow source failed YAML validation before any worker allocation. Its zero-worker failure is retained in provenance. The corrected workflow uses the same frozen authority. Original first-attempt log integers are analyzed; artifact metadata is checked, but ZIP bytes were not downloaded or independently authenticated.

## Acceptance rule

A valid admitted observation group passes only when all three raw durations are at or below its fixed budget. A campaign usefulness pass additionally requires at least 23/24 admitted allocations, at least 11/12 in each OS group, every admitted normal observation passing, and valid measured rejection of both applicable storage delay controls. The minimum is diagnostic only. Postflight cannot erase a miss.

## Core operations

| Operation | B ms | Admitted | Pass | Mixed | All over | Unqualified | Unavailable | Invalid | Raw admitted max ms | Screen |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| policy16_p1 | 20 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 13.944 | pass |
| policy16_p2 | 30 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 21.251 | pass |
| policy16_p4 | 30 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 21.924 | pass |
| policy512_p1 | 500 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 411.586 | pass |
| policy512_p2 | 350 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 348.581 | pass |
| policy512_p4 | 300 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 250.879 | pass |
| cycle48 | 50 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 40.222 | pass |
| cold16 | 125 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 59.087 | pass |
| copy16 | 20 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 1.386 | pass |

## Storage path: runner_temp

| Operation | B ms | Admitted | Pass | Mixed | All over | Unqualified | Unavailable | Invalid | Raw admitted max ms | Screen |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| copy16_sync | 100 | 24/24 | 23 | 1 | 0 | 0 | 0 | 0 | 201.936 | fail |
| atomic16_p1 | 100 | 24/24 | 23 | 1 | 0 | 0 | 0 | 0 | 217.021 | fail |
| atomic16_p2 | 100 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 75.988 | pass |
| atomic16_p4 | 100 | 24/24 | 23 | 1 | 0 | 0 | 0 | 0 | 132.455 | fail |
| append64_sync | 150 | 24/24 | 20 | 4 | 0 | 0 | 0 | 0 | 417.632 | fail |
| sqlite64_delete_full | 150 | 24/24 | 19 | 5 | 0 | 0 | 0 | 0 | 1521.636 | fail |
| sqlite64_delete_extra | 150 | 24/24 | 16 | 7 | 1 | 0 | 0 | 0 | 1334.085 | fail |
| sqlite64_wal_full | 150 | 24/24 | 23 | 1 | 0 | 0 | 0 | 0 | 226.102 | fail |
| sqlite64_delete_extra_batch | 150 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 101.057 | pass |
| sqlite64_wal_full_batch | 150 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 78.096 | pass |

## Storage path: memory

| Operation | B ms | Admitted | Pass | Mixed | All over | Unqualified | Unavailable | Invalid | Raw admitted max ms | Screen |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| copy16_sync | 100 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 0.910 | pass |
| atomic16_p1 | 100 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 0.976 | pass |
| atomic16_p2 | 100 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 4.943 | pass |
| atomic16_p4 | 100 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 6.165 | pass |
| append64_sync | 150 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 0.421 | pass |
| sqlite64_delete_full | 150 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 6.643 | pass |
| sqlite64_delete_extra | 150 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 8.406 | pass |
| sqlite64_wal_full | 150 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 3.118 | pass |
| sqlite64_delete_extra_batch | 150 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 1.127 | pass |
| sqlite64_wal_full_batch | 150 | 24/24 | 24 | 0 | 0 | 0 | 0 | 0 | 1.762 | pass |

## Storage path: distinct_mnt

| Operation | B ms | Admitted | Pass | Mixed | All over | Unqualified | Unavailable | Invalid | Raw admitted max ms | Screen |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| copy16_sync | 100 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| atomic16_p1 | 100 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| atomic16_p2 | 100 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| atomic16_p4 | 100 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| append64_sync | 150 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| sqlite64_delete_full | 150 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| sqlite64_delete_extra | 150 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| sqlite64_wal_full | 150 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| sqlite64_delete_extra_batch | 150 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |
| sqlite64_wal_full_batch | 150 | 0/24 | 0 | 0 | 0 | 0 | 24 | 0 | — | fail |

## Per-OS results

Each cell shows admitted / passing allocations out of 12, followed by the OS-group screen.

| Path | Operation | Ubuntu 24.04 | Ubuntu 22.04 |
|---|---|---|---|
| core | policy16_p1 | 12 / 12 (pass) | 12 / 12 (pass) |
| core | policy16_p2 | 12 / 12 (pass) | 12 / 12 (pass) |
| core | policy16_p4 | 12 / 12 (pass) | 12 / 12 (pass) |
| core | policy512_p1 | 12 / 12 (pass) | 12 / 12 (pass) |
| core | policy512_p2 | 12 / 12 (pass) | 12 / 12 (pass) |
| core | policy512_p4 | 12 / 12 (pass) | 12 / 12 (pass) |
| core | cycle48 | 12 / 12 (pass) | 12 / 12 (pass) |
| core | cold16 | 12 / 12 (pass) | 12 / 12 (pass) |
| core | copy16 | 12 / 12 (pass) | 12 / 12 (pass) |
| runner_temp | copy16_sync | 12 / 12 (pass) | 12 / 11 (fail) |
| runner_temp | atomic16_p1 | 12 / 12 (pass) | 12 / 11 (fail) |
| runner_temp | atomic16_p2 | 12 / 12 (pass) | 12 / 12 (pass) |
| runner_temp | atomic16_p4 | 12 / 12 (pass) | 12 / 11 (fail) |
| runner_temp | append64_sync | 12 / 12 (pass) | 12 / 8 (fail) |
| runner_temp | sqlite64_delete_full | 12 / 12 (pass) | 12 / 7 (fail) |
| runner_temp | sqlite64_delete_extra | 12 / 11 (fail) | 12 / 5 (fail) |
| runner_temp | sqlite64_wal_full | 12 / 12 (pass) | 12 / 11 (fail) |
| runner_temp | sqlite64_delete_extra_batch | 12 / 12 (pass) | 12 / 12 (pass) |
| runner_temp | sqlite64_wal_full_batch | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | copy16_sync | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | atomic16_p1 | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | atomic16_p2 | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | atomic16_p4 | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | append64_sync | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | sqlite64_delete_full | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | sqlite64_delete_extra | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | sqlite64_wal_full | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | sqlite64_delete_extra_batch | 12 / 12 (pass) | 12 / 12 (pass) |
| memory | sqlite64_wal_full_batch | 12 / 12 (pass) | 12 / 12 (pass) |
| distinct_mnt | copy16_sync | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | atomic16_p1 | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | atomic16_p2 | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | atomic16_p4 | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | append64_sync | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | sqlite64_delete_full | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | sqlite64_delete_extra | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | sqlite64_wal_full | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | sqlite64_delete_extra_batch | 0 / 0 (fail) | 0 / 0 (fail) |
| distinct_mnt | sqlite64_wal_full_batch | 0 / 0 (fail) | 0 / 0 (fail) |

## Path availability and mount evidence

### runner_temp

Available on 24/24 allocations. Filesystems: `{'ext4': 24}`. Observed device-number distribution: `{'259:1': 10, '8:1': 6, '252:0': 8}`.

Durability cautions: `{'journal_async_commit': 24, 'nobarrier': 24, 'data=writeback': 24}`. These are observed configuration facts, not a power-loss test.

```json
{
  "actual_filesystems": {
    "ext4": 24
  },
  "available_count": 24,
  "block_models_visible_on_workers": {
    "Amazon EC2 NVMe Instance Storage": 8,
    "Amazon Elastic Block Store": 8,
    "MSFT NVMe Accelerator v1.0": 10,
    "Virtual Disk": 6
  },
  "mount_option_sets": {
    "rw,relatime,discard,journal_async_commit,nobarrier,errors=remount-ro,commit=30,data=writeback": 24
  },
  "mount_sources": {
    "/dev/mapper/cow-root": 8,
    "/dev/nvme0n1p1": 10,
    "/dev/sda1": 6
  },
  "sqlite_versions": {
    "3.37.2": 12,
    "3.45.1": 12
  }
}
```

### memory

Available on 24/24 allocations. Filesystems: `{'tmpfs': 24}`. Observed device-number distribution: `{'0:27': 4, '0:30': 8, '0:25': 12}`.

Durability cautions: `{'volatile_filesystem': 24}`. These are observed configuration facts, not a power-loss test.

```json
{
  "actual_filesystems": {
    "tmpfs": 24
  },
  "available_count": 24,
  "block_models_visible_on_workers": {
    "Amazon EC2 NVMe Instance Storage": 8,
    "Amazon Elastic Block Store": 8,
    "MSFT NVMe Accelerator v1.0": 10,
    "Virtual Disk": 6
  },
  "mount_option_sets": {
    "rw,nosuid,nodev,inode64": 24
  },
  "mount_sources": {
    "tmpfs": 24
  },
  "sqlite_versions": {
    "3.37.2": 12,
    "3.45.1": 12
  }
}
```

### distinct_mnt

Available on 0/24 allocations. Filesystems: `{}`. Observed device-number distribution: `{}`.

Durability cautions: `{}`. These are observed configuration facts, not a power-loss test.

```json
{
  "actual_filesystems": {},
  "available_count": 0,
  "block_models_visible_on_workers": {},
  "mount_option_sets": {},
  "mount_sources": {},
  "sqlite_versions": {}
}
```

Unavailable allocations and recorded reasons:

```json
{
  "1": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "10": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "11": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "12": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "13": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "14": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "15": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "16": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "17": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "18": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "19": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "2": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "20": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "21": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "22": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "23": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "24": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "3": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "4": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "5": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "6": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "7": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "8": "no writable distinct mounted device at /mnt; no duplicate root-disk arm",
  "9": "no writable distinct mounted device at /mnt; no duplicate root-disk arm"
}
```

## Controls

Only verified complete executions with the specified injected delay and an actually measured over-budget result count as proven rejection. Invalid executions are separate.

| Path | Control | Admitted | Proven rejects | Invalid executions |
|---|---|---:|---:|---:|
| runner_temp | atomic16_p1/wait | 24 | 24 | 0 |
| runner_temp | sqlite64_wal_full/periodic_wait | 24 | 24 | 0 |
| memory | atomic16_p1/wait | 24 | 24 | 0 |
| memory | sqlite64_wal_full/periodic_wait | 24 | 24 | 0 |
| distinct_mnt | atomic16_p1/wait | 0 | 0 | 0 |
| distinct_mnt | sqlite64_wal_full/periodic_wait | 0 | 0 | 0 |

## Every admitted normal miss

```json
{
  "all_over_groups": 1,
  "allocation_ids": [
    1,
    13,
    15,
    17,
    18,
    19,
    21,
    22,
    24
  ],
  "minimum_would_hide_groups": 20,
  "mixed_groups": 20,
  "over_budget_observations": 27,
  "worker_case_groups": 21
}
```

| Allocation | Path | Operation | Raw observations ms | Verdict |
|---:|---|---|---|---|
| 1 | runner_temp | sqlite64_delete_extra/normal | 69.674, 63.340, 204.757 | mixed_miss |
| 13 | runner_temp | copy16_sync/normal | 31.168, 5.007, 201.936 | mixed_miss |
| 13 | runner_temp | atomic16_p1/normal | 57.827, 36.331, 217.021 | mixed_miss |
| 13 | runner_temp | append64_sync/normal | 36.131, 39.177, 399.091 | mixed_miss |
| 13 | runner_temp | sqlite64_delete_full/normal | 81.868, 133.038, 1521.636 | mixed_miss |
| 13 | runner_temp | sqlite64_delete_extra/normal | 580.807, 174.757, 1334.085 | all_over |
| 13 | runner_temp | sqlite64_wal_full/normal | 226.102, 54.624, 52.664 | mixed_miss |
| 15 | runner_temp | sqlite64_delete_extra/normal | 105.866, 332.621, 91.052 | mixed_miss |
| 17 | runner_temp | sqlite64_delete_extra/normal | 74.628, 489.967, 130.843 | mixed_miss |
| 18 | runner_temp | append64_sync/normal | 42.946, 338.745, 12.752 | mixed_miss |
| 18 | runner_temp | sqlite64_delete_full/normal | 55.191, 241.436, 50.368 | mixed_miss |
| 19 | runner_temp | sqlite64_delete_full/normal | 128.344, 115.961, 158.168 | mixed_miss |
| 19 | runner_temp | sqlite64_delete_extra/normal | 104.739, 428.488, 226.320 | mixed_miss |
| 21 | runner_temp | sqlite64_delete_full/normal | 446.370, 54.207, 44.802 | mixed_miss |
| 21 | runner_temp | sqlite64_delete_extra/normal | 199.947, 165.911, 52.987 | mixed_miss |
| 22 | runner_temp | atomic16_p4/normal | 12.806, 132.455, 15.948 | mixed_miss |
| 22 | runner_temp | append64_sync/normal | 201.782, 417.632, 15.241 | mixed_miss |
| 22 | runner_temp | sqlite64_delete_full/normal | 401.640, 104.187, 72.236 | mixed_miss |
| 22 | runner_temp | sqlite64_delete_extra/normal | 183.410, 154.918, 100.016 | mixed_miss |
| 24 | runner_temp | append64_sync/normal | 24.570, 388.397, 15.968 | mixed_miss |
| 24 | runner_temp | sqlite64_delete_extra/normal | 172.311, 110.937, 82.762 | mixed_miss |

## Generic probe evidence

The sync probe remains diagnostic. It grants no physical persistence qualification.

| Phase | Probe | Cap ms | Raw min ms | Raw median ms | Raw max ms | Over-cap allocations |
|---|---|---:|---:|---:|---:|---|
| preflight | cpu_serial | 350 | 137.203 | 206.714 | 281.896 | [] |
| preflight | cpu_p4 | 300 | 72.051 | 102.352 | 167.572 | [] |
| preflight | sha256 | 250 | 126.353 | 148.383 | 189.281 | [] |
| preflight | warm_files | 150 | 30.129 | 72.117 | 118.793 | [] |
| preflight | fdatasync64 | 250 | 11.378 | 21.900 | 660.383 | [8, 9] |
| postflight | cpu_serial | 350 | 137.722 | 205.174 | 281.925 | [] |
| postflight | cpu_p4 | 300 | 69.917 | 100.318 | 144.166 | [] |
| postflight | sha256 | 250 | 127.211 | 148.314 | 185.605 | [] |
| postflight | warm_files | 150 | 29.896 | 71.382 | 110.107 | [] |
| postflight | fdatasync64 | 250 | 8.815 | 16.863 | 148.097 | [] |

## Resources and cost

```json
{
  "harness_ms": {
    "count": 24,
    "maximum": 14128.994415,
    "median": 8713.6225195,
    "minimum": 6234.052333
  },
  "resources": {
    "cpu_model": {
      "AMD EPYC 7763 64-Core Processor": 6,
      "AMD EPYC 9V45 96-Core Processor": 3,
      "AMD EPYC 9V74 80-Core Processor": 6,
      "INTEL(R) XEON(R) PLATINUM 8573C": 1,
      "Intel(R) Xeon(R) 6975P-C": 8
    },
    "filesystem": {
      "ext2/ext3": 24
    },
    "image_os": {
      "ubuntu22": 12,
      "ubuntu24": 12
    },
    "image_version": {
      "20261116.133.1": 6,
      "20261116.365.1": 8,
      "20261116.376.1": 2,
      "20261122.23.1": 4,
      "20261122.372.1": 4
    },
    "kernel": {
      "6.8.0-1070-azure": 8,
      "6.8.0-1073-azure": 4,
      "7.0.0-1014-aws": 6,
      "7.0.0-1017-azure": 2,
      "7.0.0-1018-aws": 2,
      "7.0.0-1020-azure": 2
    },
    "python": {
      "3.11.9": 24
    }
  }
}
```

Harness cost includes preparation, verification and reset, generic probes, normal cases and deliberate waits. It is not the cost of a minimal CI gate.

## Evidence errors

```json
{
  "collection": [],
  "record_validation": [],
  "validation": []
}
```

## Scope

These fixed numbers demonstrate a raw timing protocol; they do not become Riverhog or Fishhat's design budgets. The batch cases change acknowledgment granularity. The legacy cases retain their original namespace synchronization limitations. Single-connection SQLite evidence does not qualify concurrent database use. A same-day finite campaign does not establish later-date reliability or a bound on rare latency tails. Passing on tmpfs or relaxed native mounts cannot satisfy a stronger physical durability requirement.

The two OS groups also differ in SQLite library version, kernels and hardware; this campaign does not identify the OS itself as the cause of any difference. Unavailable /mnt means no qualifying preexisting writable path there. Other block devices visible in lsblk were not reconfigured or qualified.
