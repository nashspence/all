"""Check already observed evidence and justified work limits; never run a workload."""
from typing import Mapping, Sequence

Receipts = Sequence[tuple[str, str]]


def check_observation(
    scope_ids: Sequence[str],
    expected: Receipts,
    actual: Receipts,
    observed: Mapping[str, int],
    limits: Mapping[str, int],
) -> list[str]:
    """One small, passive check of the owner's existing evidence and counters.

    The owner establishes the inventory, independent expected outcomes, actual
    cohort, instrumentation and justified limits. Include enforcement work in
    the selected counters. No callback, profiler, matrix or second run is needed.
    """
    names = set(scope_ids)
    if not names or len(names) != len(scope_ids) or "" in names:
        raise ValueError("expected nonempty unique scope identities")
    if not limits:
        raise ValueError("expected selected work limits")
    for metric, limit in limits.items():
        if not metric or type(limit) is not int or limit < 0:
            raise ValueError("invalid work limit")
    for metric, amount in observed.items():
        if metric not in limits or type(amount) is not int or amount < 0:
            raise ValueError("invalid work observation")

    def index(receipts: Receipts):
        if len(receipts) != len(names):
            return None
        result = dict(receipts)
        return result if result.keys() == names else None

    wanted = index(expected)
    if wanted is None:
        raise ValueError("expected evidence does not cover the scope inventory")
    got = index(actual)
    errors = []
    if got is None or got != wanted:
        errors.append("incomplete or incorrect scope evidence")
    for metric, limit in limits.items():
        if metric not in observed:
            errors.append(f"missing work observation: {metric}")
        elif observed[metric] > limit:
            errors.append(f"{metric}: {observed[metric]} > {limit}")
    return errors
