"""Small synthetic witness; optional standalone demo, not an extra CI gate."""
from hashlib import sha256
from io import BytesIO

from policy import check_observation

# A fixed, deliberately small witness, not a matrix derived from repository size.
# Vary one axis at a time, then one joint case to expose cross-products.
SAMPLES = ((4, 64, 0), (16, 64, 0), (4, 256, 0), (4, 64, 1024), (16, 256, 1024))
MUTANTS = {
    "whole-report": "reader-read-bytes",
    "repeated-setup": "reader-hash-bytes",
    "repeated-oracle": "oracle-hash-bytes",
}


def run_case(n, shared_size, extra, mode="partitioned"):
    if mode not in ("partitioned", *MUTANTS):
        raise ValueError("unknown synthetic reader")
    # Count logical bytes at actual operations, including the fixture and the
    # independent verifier. No timing threshold or physical I/O claim.
    counts = {}

    def charge(metric, amount):
        counts[metric] = counts.get(metric, 0) + amount

    names = tuple(f"scope-{i}" for i in range(n))
    shared = b"s" * shared_size
    charge("fixture-bytes", len(shared))
    originals = []
    for i in range(n):
        original = bytes([i]) * (32 + (extra if i == 0 else 0))
        charge("fixture-bytes", len(original))
        originals.append(original)
    originals = tuple(originals)

    def read(data):
        value = BytesIO(data).read()
        charge("reader-read-bytes", len(value))
        return value

    def reader_hash(data):
        digest = sha256(data).digest()
        charge("reader-hash-bytes", len(data))
        return digest

    common = None if mode == "repeated-setup" else reader_hash(read(shared))
    report = b"".join(originals) if mode == "whole-report" else None
    actual = []
    offset = 0
    for name, original in zip(names, originals):
        prefix = reader_hash(read(shared)) if common is None else common
        data = read(original) if report is None else read(report)[offset:offset + len(original)]
        actual.append((name, reader_hash(prefix + data).hex()))
        offset += len(original)

    # Independent digest construction: no producer results, reader helpers or
    # previously computed producer digest are reused. Hash shared input ONCE.
    # The explicit bad-oracle branch is a negative control, never a default.
    def oracle_shared():
        digest = sha256(shared).digest()
        charge("oracle-hash-bytes", len(shared))
        return digest

    prefix = None if mode == "repeated-oracle" else oracle_shared()
    expected = []
    for name, original in zip(names, originals):
        initial = oracle_shared() if prefix is None else prefix
        digest = sha256(initial)
        digest.update(original)
        charge("oracle-hash-bytes", len(initial) + len(original))
        expected.append((name, digest.hexdigest()))

    # Derived from the intended operations, not the observations: generate
    # inputs once, read once, hash each input once per independent participant,
    # plus one 32-byte digest prefix per receipt in each participant.
    total = shared_size + 32 * n + extra
    limits = {
        "fixture-bytes": total,
        "reader-read-bytes": total,
        "reader-hash-bytes": total + 32 * n,
        "oracle-hash-bytes": total + 32 * n,
    }
    errors = check_observation(names, expected, actual, counts, limits)
    return errors, counts, limits


if __name__ == "__main__":
    for sample in SAMPLES:
        errors, observed, limits = run_case(*sample)
        assert not errors, errors
        print(f"partitioned {sample}: {observed}")
    for mode, metric in MUTANTS.items():
        errors, observed, limits = run_case(*SAMPLES[-1], mode=mode)
        assert errors and all(error.split(":")[0] in
                              ("reader-read-bytes", "reader-hash-bytes", "oracle-hash-bytes")
                              for error in errors), errors
        assert observed[metric] > limits[metric]
        print(f"{mode}: {'; '.join(errors)} (complete correct evidence)")
