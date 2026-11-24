"""Check one complete execution against an independently collected case plan.

The owning runner supplies actual phase outcomes and verifies source/provenance.
This helper never assembles arbitrary receipts. Sharded or reused-job artifacts
need a local custody adapter that establishes one compatible logical execution;
that need not mean every artifact has the same GitHub attempt number.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable


def _cases(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("a collection of case identities is required")
    cases = tuple(values)
    if not cases or any(not isinstance(case, str) or not case for case in cases):
        raise ValueError("case identities must be nonempty strings")
    if len(set(cases)) != len(cases):
        raise ValueError("duplicate case identity")
    return tuple(sorted(cases))


@dataclass(frozen=True)
class Plan:
    source: str
    profile: str
    cases: tuple[str, ...]

    @property
    def identity(self) -> str:
        if not self.source or not self.profile:
            raise ValueError("source and execution profile are required")
        data = [self.source, self.profile, _cases(self.cases)]
        return hashlib.sha256(json.dumps(data, ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class Case:
    identity: str
    execution: str
    setup: str
    call: str
    teardown: str


@dataclass(frozen=True)
class Execution:
    identity: str
    source: str
    profile: str
    plan: str
    cases: tuple[Case, ...]


def require_complete(plan: Plan, execution: Execution) -> None:
    if not execution.identity:
        raise ValueError("execution origin is required")
    if (execution.source, execution.profile, execution.plan) != (
        plan.source, plan.profile, plan.identity
    ):
        raise ValueError("source, profile or collection plan differs")
    if _cases(case.identity for case in execution.cases) != _cases(plan.cases):
        raise ValueError("execution does not contain exactly the collected cases")
    for case in execution.cases:
        if case.execution != execution.identity:
            raise ValueError("cannot combine successes from separate executions")
        if (case.setup, case.call, case.teardown) != ("passed",) * 3:
            raise ValueError(f"incomplete or unsuccessful phases: {case.identity}")
