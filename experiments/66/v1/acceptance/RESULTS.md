# Prepared storage campaign analysis

Run 45716944073; phase **acceptance**; source `bea509359a6abb2f42f56ae5ef15622ed4a3d292`.

**Resource qualification: not_qualified.** Resource workers passing: 8/12; workers with both consumers correct: 8/12.

Complete verified generic observations: 216/288; consumer observations: 54/72.

| Observed quantity | Count | Minimum ms | Maximum ms | Median ms |
|---|---:|---:|---:|---:|
| consumer/fishhat | 27 | 10.535 | 27.067 | 11.710 |
| consumer/riverhog | 27 | 11.078 | 25.911 | 13.018 |
| consumer_stage/fishhat/drain_ns | 9 | 19.459 | 31.660 | 27.047 |
| consumer_stage/fishhat/startup_ns | 9 | 221.571 | 398.238 | 259.361 |
| consumer_stage/fishhat/verification_ns | 27 | 0.802 | 1.512 | 0.971 |
| consumer_stage/riverhog/drain_ns | 9 | 111.222 | 192.638 | 130.799 |
| consumer_stage/riverhog/startup_ns | 9 | 2120.021 | 3310.437 | 2443.098 |
| consumer_stage/riverhog/verification_ns | 27 | 0.937 | 5.352 | 1.587 |
| cost/bootstrap | 11 | 5558.903 | 9910.323 | 7689.157 |
| cost/controller | 11 | 18123.635 | 35837.750 | 24502.233 |
| cost/setup_cleanup | 11 | 1050.880 | 3263.051 | 1652.033 |
| generic/append64_sync | 27 | 14.351 | 45.691 | 17.676 |
| generic/atomic16_p1 | 27 | 8.269 | 28.752 | 13.953 |
| generic/atomic16_p2 | 27 | 7.536 | 229.580 | 11.943 |
| generic/atomic16_p4 | 27 | 5.453 | 15.131 | 6.650 |
| generic/sqlite64_delete_extra | 27 | 52.170 | 149.302 | 60.183 |
| generic/sqlite64_delete_extra_batch | 27 | 2.665 | 5.717 | 3.146 |
| generic/sqlite64_wal_full | 27 | 19.993 | 47.622 | 21.457 |
| generic/sqlite64_wal_full_batch | 27 | 3.480 | 7.574 | 3.972 |
| generic_stage/drain_fixture_cleanup_ns | 216 | 10.887 | 21.834 | 16.148 |
| generic_stage/startup_prepare_ns | 216 | 143.324 | 251.634 | 150.153 |
| generic_stage/verification_reset_ns | 216 | 0.572 | 84.778 | 0.911 |

## Failures and consumer target misses

- missing/extra worker files
- distinct worker runner identities required
- worker-1: FileNotFoundError: [Errno 2] No such file or directory: 'experiments/66/v1/acceptance/worker-1.json'
- worker-4: GitHub job missing or not successful
- worker-4: controller/collection errors
- worker-4: collection/generic command incomplete
- worker-4: postflight/root_loop_a: unqualified
- worker-4: postflight/root_loop_a/paired/fdatasync64/0: invalid/over-cap
- worker-7: GitHub job missing or not successful
- worker-7: controller/collection errors
- worker-7: collection/generic command incomplete
- worker-7: preflight/root_loop_b: unqualified
- worker-7: preflight/root_loop_b/cpu_serial/1: invalid/over-cap
- worker-7: postflight/root_loop_a: unqualified
- worker-7: postflight/root_loop_a/paired/cpu_serial/0: invalid/over-cap
- worker-7: generic shared: module hashes
- worker-7: generic shared: source aggregate/runtime
- worker-7: generic shared: shared package identity
- worker-7: generic shared: shared module tuple differs
- worker-7: generic packet/extent/placement
- worker-7: atomic16_p1: fixed screen changed
- worker-7: atomic16_p1: exactly three observations required
- worker-7: atomic16_p2: fixed screen changed
- worker-7: atomic16_p2: exactly three observations required
- worker-7: atomic16_p4: fixed screen changed
- worker-7: atomic16_p4: exactly three observations required
- worker-7: append64_sync: fixed screen changed
- worker-7: append64_sync: exactly three observations required
- worker-7: sqlite64_delete_extra: fixed screen changed
- worker-7: sqlite64_delete_extra: exactly three observations required
- worker-7: sqlite64_wal_full: fixed screen changed
- worker-7: sqlite64_wal_full: exactly three observations required
- worker-7: sqlite64_delete_extra_batch: fixed screen changed
- worker-7: sqlite64_delete_extra_batch: exactly three observations required
- worker-7: sqlite64_wal_full_batch: fixed screen changed
- worker-7: sqlite64_wal_full_batch: exactly three observations required
- worker-7: both consumer packets required
- worker-7: fishhat: consumer execution incomplete
- worker-7: fishhat: source/dependency pin mismatch
- worker-7: fishhat shared: module hashes
- worker-7: fishhat shared: source aggregate/runtime
- worker-7: fishhat shared: shared package identity
- worker-7: fishhat shared: shared module tuple differs
- worker-7: fishhat: normal product module/runtime pin
- worker-7: fishhat: reviewed binding hashes
- worker-7: fishhat: actual worker did not inspect the same prepared resource
- worker-7: fishhat: exactly three observations required
- worker-7: fishhat: three retained verifications required
- worker-7: fishhat: missing startup_ns
- worker-7: fishhat: missing drain_ns
- worker-7: riverhog: consumer execution incomplete
- worker-7: riverhog: source/dependency pin mismatch
- worker-7: riverhog shared: module hashes
- worker-7: riverhog shared: source aggregate/runtime
- worker-7: riverhog shared: shared package identity
- worker-7: riverhog shared: shared module tuple differs
- worker-7: riverhog: normal product module/runtime pin
- worker-7: riverhog: reviewed binding hashes
- worker-7: riverhog: actual worker did not inspect the same prepared resource
- worker-7: riverhog: exactly three observations required
- worker-7: riverhog: three retained verifications required
- worker-7: riverhog: missing startup_ns
- worker-7: riverhog: missing drain_ns
- worker-12: GitHub job missing or not successful
- worker-12: controller/collection errors
- worker-12: collection/generic command incomplete
- worker-12: preflight/root_loop_a: unqualified
- worker-12: preflight/root_loop_a/fdatasync64/1: invalid/over-cap
- worker-12: generic shared: module hashes
- worker-12: generic shared: source aggregate/runtime
- worker-12: generic shared: shared package identity
- worker-12: generic shared: shared module tuple differs
- worker-12: generic packet/extent/placement
- worker-12: atomic16_p1: fixed screen changed
- worker-12: atomic16_p1: exactly three observations required
- worker-12: atomic16_p2: fixed screen changed
- worker-12: atomic16_p2: exactly three observations required
- worker-12: atomic16_p4: fixed screen changed
- worker-12: atomic16_p4: exactly three observations required
- worker-12: append64_sync: fixed screen changed
- worker-12: append64_sync: exactly three observations required
- worker-12: sqlite64_delete_extra: fixed screen changed
- worker-12: sqlite64_delete_extra: exactly three observations required
- worker-12: sqlite64_wal_full: fixed screen changed
- worker-12: sqlite64_wal_full: exactly three observations required
- worker-12: sqlite64_delete_extra_batch: fixed screen changed
- worker-12: sqlite64_delete_extra_batch: exactly three observations required
- worker-12: sqlite64_wal_full_batch: fixed screen changed
- worker-12: sqlite64_wal_full_batch: exactly three observations required
- worker-12: both consumer packets required
- worker-12: fishhat: consumer execution incomplete
- worker-12: fishhat: source/dependency pin mismatch
- worker-12: fishhat shared: module hashes
- worker-12: fishhat shared: source aggregate/runtime
- worker-12: fishhat shared: shared package identity
- worker-12: fishhat shared: shared module tuple differs
- worker-12: fishhat: normal product module/runtime pin
- worker-12: fishhat: reviewed binding hashes
- worker-12: fishhat: actual worker did not inspect the same prepared resource
- worker-12: fishhat: exactly three observations required
- worker-12: fishhat: three retained verifications required
- worker-12: fishhat: missing startup_ns
- worker-12: fishhat: missing drain_ns
- worker-12: riverhog: consumer execution incomplete
- worker-12: riverhog: source/dependency pin mismatch
- worker-12: riverhog shared: module hashes
- worker-12: riverhog shared: source aggregate/runtime
- worker-12: riverhog shared: shared package identity
- worker-12: riverhog shared: shared module tuple differs
- worker-12: riverhog: normal product module/runtime pin
- worker-12: riverhog: reviewed binding hashes
- worker-12: riverhog: actual worker did not inspect the same prepared resource
- worker-12: riverhog: exactly three observations required
- worker-12: riverhog: three retained verifications required
- worker-12: riverhog: missing startup_ns
- worker-12: riverhog: missing drain_ns

All required raw observations must pass. Means/minima are diagnostics. Consumer320ms misses do not disqualify a resource. No crash/release proof follows.

This analysis recomputes recorded numerical/completion gates and source identities; it does not rerun native operations. GitHub job outcomes come from the separately retained manifest. Approval remains a versioned repository decision.
