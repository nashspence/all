"""Deterministic synthetic evidence-reader experiment; not a native CI benchmark."""
from hashlib import sha256
from io import BytesIO

from policy import Bound, Case, Scope, check_matrix

# Derived from the operations below: one read/hash of the shared immutable
# input, one read/hash of each required original. Counts are byte-work, not
# a proxy for wall-clock, filesystem allocation or authorization.
BOUNDS = {"shared-read-bytes": Bound(per_shared_byte=1),
          "evidence-read-bytes": Bound(per_original_byte=1)}


def cases():
    # Vary scope count independently of common input size and a single scope's
    # original extent. Other originals stay byte-identical when axes change.
    return [Case(b"s" * shared_size,
                 tuple(Scope(f"scope-{i}", bytes([i]) * (32 + (extra if i == 0 else 0)))
                       for i in range(n)))
            for n in (1, 4, 16) for shared_size in (64, 256) for extra in (0, 1024)]


def oracle(case):
    # Separate from either reader topology; no measured counters originate here.
    return [(s.name, sha256(sha256(case.shared).digest() + s.original).hexdigest())
            for s in case.scopes]


def read(data, metric, charge):
    payload = BytesIO(data).read()
    charge(metric, len(payload))
    return payload


def execute(case, charge, *, whole_report=False, repeated_setup=False):
    shared = None if repeated_setup else sha256(read(case.shared, "shared-read-bytes", charge)).digest()
    report = b"".join(s.original for s in case.scopes) if whole_report else None
    offset = 0
    receipts = []
    for scope in case.scopes:
        digest = (sha256(read(case.shared, "shared-read-bytes", charge)).digest()
                  if repeated_setup else shared)
        if whole_report:
            data = read(report, "evidence-read-bytes", charge)[offset:offset + len(scope.original)]
        else:
            data = read(scope.original, "evidence-read-bytes", charge)
        receipts.append((scope.name, sha256(digest + data).hexdigest()))
        offset += len(scope.original)
    return receipts


def report_reader(case, charge):
    return execute(case, charge, whole_report=True)


def setup_reader(case, charge):
    return execute(case, charge, repeated_setup=True)


if __name__ == "__main__":
    samples = cases()
    assert not check_matrix(samples, execute, oracle, BOUNDS)
    for reader in (report_reader, setup_reader):
        # Both mutants produce the exact same complete results, not weaker proof.
        assert all(reader(c, lambda *_: None) == oracle(c) for c in samples)
        failures = check_matrix(samples, reader, oracle, BOUNDS)
        assert failures
        print(f"{reader.__name__}: {len(failures)} bound violations; {failures[-1]}")
    print(f"{len(samples)} partitioned cases passed with equivalent complete evidence")
