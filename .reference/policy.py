"""Require a disjoint, exhaustive partition of current collected case IDs.

The owner independently verifies raw artifact custody and supplies each shard's
accepted origin. Reused completed jobs may have different attempt IDs. This
checks assignment and provenance equality, not assertion outcomes or authority.
"""

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("expected a collection of case IDs")
    values = tuple(values)
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError("identities must be nonempty strings")
    if len(set(values)) != len(values):
        raise ValueError("duplicate case ID")
    return tuple(sorted(values))


def plan_identity(source: str, conditions: str, assignments: Mapping[str, Iterable[str]]) -> str:
    if not source or not conditions or not assignments:
        raise ValueError("source, conditions and shard assignments are required")
    rows = [(shard, _unique(cases)) for shard, cases in sorted(assignments.items())]
    if any(not isinstance(shard, str) or not shard for shard, _ in rows):
        raise ValueError("shard IDs must be nonempty strings")
    data = json.dumps([source, conditions, rows], ensure_ascii=True).encode()
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Shard:
    name: str
    source: str
    conditions: str
    plan: str
    origin: str
    cases: tuple[str, ...]


def require_partition(
    collected: Iterable[str], assignments: Mapping[str, Iterable[str]],
    shards: Iterable[Shard], *, source: str, conditions: str,
    accepted_origins: Mapping[str, str],
) -> None:
    expected = _unique(collected)
    assignments = {name: _unique(cases) for name, cases in assignments.items()}
    plan = plan_identity(source, conditions, assignments)
    assigned = [case for cases in assignments.values() for case in cases]
    if _unique(assigned) != expected:
        raise ValueError("assignments are not an exact partition of current collection")
    shards = tuple(shards)
    names = Counter(shard.name for shard in shards)
    if set(names) != set(assignments) or any(count != 1 for count in names.values()):
        raise ValueError("every planned shard needs exactly one execution record")
    if set(accepted_origins) != set(assignments) or any(not origin for origin in accepted_origins.values()):
        raise ValueError("owner-verified origins are required for every shard")
    for shard in shards:
        if (shard.source, shard.conditions, shard.plan, shard.origin) != (
            source, conditions, plan, accepted_origins[shard.name]
        ):
            raise ValueError("shard source, conditions, plan or origin differs")
        if _unique(shard.cases) != assignments[shard.name]:
            raise ValueError("executed shard differs from its planned cases")
