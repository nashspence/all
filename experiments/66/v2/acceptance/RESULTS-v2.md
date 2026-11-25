# Prepared storage v2 campaign analysis

Run 45718971162; phase **acceptance**; source `5086428a29871eeb267ea7225537aa0225930bac`.

**Resource qualification: passed.** Resource workers passing: 12/12; workers with both consumers correct: 12/12.

Complete verified generic observations: 288/288; consumer observations: 72/72.

| Observed quantity | Count | Minimum ms | Maximum ms | Median ms |
|---|---:|---:|---:|---:|
| consumer/fishhat | 36 | 9.414 | 605.141 | 13.826 |
| consumer/riverhog | 36 | 10.871 | 69.181 | 14.864 |
| consumer_stage/fishhat/drain_ns | 12 | 23.454 | 33.472 | 28.878 |
| consumer_stage/fishhat/startup_ns | 12 | 253.647 | 382.915 | 285.869 |
| consumer_stage/fishhat/verification_ns | 36 | 0.870 | 1.615 | 1.136 |
| consumer_stage/riverhog/drain_ns | 12 | 108.090 | 205.231 | 148.774 |
| consumer_stage/riverhog/startup_ns | 12 | 2241.528 | 3554.605 | 2604.675 |
| consumer_stage/riverhog/verification_ns | 36 | 0.944 | 8.228 | 1.807 |
| cost/bootstrap | 12 | 6271.285 | 12060.447 | 7685.057 |
| cost/controller | 12 | 23521.125 | 38395.967 | 29332.803 |
| cost/setup_cleanup | 12 | 997.694 | 3823.413 | 1650.273 |
| generic/append64_sync | 36 | 14.614 | 153.543 | 21.023 |
| generic/atomic16_p1 | 36 | 7.523 | 119.234 | 13.992 |
| generic/atomic16_p2 | 36 | 7.411 | 84.857 | 12.492 |
| generic/atomic16_p4 | 36 | 5.640 | 35.652 | 7.367 |
| generic/sqlite64_delete_extra | 36 | 53.996 | 496.986 | 71.119 |
| generic/sqlite64_delete_extra_batch | 36 | 2.662 | 78.914 | 3.476 |
| generic/sqlite64_wal_full | 36 | 18.170 | 134.138 | 26.849 |
| generic/sqlite64_wal_full_batch | 36 | 3.445 | 14.710 | 4.873 |
| generic_stage/drain_fixture_cleanup_ns | 288 | 12.962 | 24.979 | 17.130 |
| generic_stage/startup_prepare_ns | 288 | 143.618 | 569.313 | 172.674 |
| generic_stage/verification_reset_ns | 288 | 0.557 | 205.000 | 1.028 |

## Historical probe caps: diagnostics only

These caps belonged to v1. V2 claims no probe latency guarantee; all probe observations and correctness remain required.

| Probe | Count | Maximum ms | Historical cap ms | Above historical cap |
|---|---:|---:|---:|---:|
| cpu_serial | 288 | 353.234 | 350.000 | 1 |
| cpu_p4 | 288 | 215.821 | 300.000 | 0 |
| sha256 | 288 | 210.623 | 250.000 | 0 |
| warm_files | 288 | 110.870 | 150.000 | 0 |
| fdatasync64 | 288 | 625.465 | 250.000 | 9 |

- Diagnostic worker-1/preflight/root_loop_b/fdatasync64/1: 357.987 ms; historical cap 250.000 ms.
- Diagnostic worker-3/preflight/root_loop_a/fdatasync64/0: 625.465 ms; historical cap 250.000 ms.
- Diagnostic worker-3/postflight/root_loop_a/fdatasync64/2: 362.574 ms; historical cap 250.000 ms.
- Diagnostic worker-3/postflight/root_loop_a/paired/fdatasync64/1: 452.763 ms; historical cap 250.000 ms.
- Diagnostic worker-5/preflight/root_loop_a/fdatasync64/1: 260.397 ms; historical cap 250.000 ms.
- Diagnostic worker-5/preflight/root_loop_a/paired/fdatasync64/1: 332.057 ms; historical cap 250.000 ms.
- Diagnostic worker-5/preflight/root_loop_b/paired/fdatasync64/1: 317.000 ms; historical cap 250.000 ms.
- Diagnostic worker-7/preflight/root_loop_a/paired/cpu_serial/0: 353.234 ms; historical cap 350.000 ms.
- Diagnostic worker-7/postflight/root_loop_a/fdatasync64/1: 488.258 ms; historical cap 250.000 ms.
- Diagnostic worker-7/postflight/root_loop_b/fdatasync64/0: 447.559 ms; historical cap 250.000 ms.

## Failures and consumer target misses

- fishhat320ms engineering misses: worker-7/0, worker-7/1

V2 admits the declared resource configuration and requires complete correct raw probes; probe latencies are diagnostic. Every actual generic storage operation must meet its unchanged fixed maximum. Means/minima never rescue an operation miss. Consumer320ms misses remain separate. V1 verdicts are unchanged. No crash/release proof follows.

This analysis recomputes recorded numerical/completion gates and source identities; it does not rerun native operations. GitHub job outcomes come from the separately retained manifest. Approval remains a versioned repository decision.
