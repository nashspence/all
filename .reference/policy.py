"""Finite composition checks on actual validation work, not elapsed time."""
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class Scope:
    name: str
    original: bytes


@dataclass(frozen=True)
class Case:
    shared: bytes
    scopes: tuple[Scope, ...]


@dataclass(frozen=True)
class Bound:
    fixed: int = 0
    per_scope: int = 0
    per_original_byte: int = 0
    per_shared_byte: int = 0

    def limit(self, case: Case) -> int:
        return (self.fixed + self.per_scope * len(case.scopes)
                + self.per_original_byte * sum(len(s.original) for s in case.scopes)
                + self.per_shared_byte * len(case.shared))


Receipts = Sequence[tuple[str, str]]
Charge = Callable[[str, int], None]


def check_case(case: Case, execute: Callable[[Case, Charge], Receipts],
               oracle: Callable[[Case], Receipts], bounds: Mapping[str, Bound]) -> list[str]:
    """Execute the entire case; check complete independent results and measured work.

    The owner supplies the real execution adapter, independent oracle, actual
    immutable inputs, justified coefficients and complete counter instrumentation.
    This finite witness does not infer scope independence or prove asymptotics.
    """
    names = [s.name for s in case.scopes]
    if not names or len(set(names)) != len(names) or any(not n for n in names):
        raise ValueError("expected nonempty, unique scope identities")
    if not bounds:
        raise ValueError("expected at least one work bound")
    for name, bound in bounds.items():
        if not name or any(type(v) is not int or v < 0 for v in
                           (bound.fixed, bound.per_scope, bound.per_original_byte,
                            bound.per_shared_byte)):
            raise ValueError("invalid work bound")

    observed: dict[str, int] = {}

    def charge(metric: str, amount: int) -> None:
        if metric not in bounds or type(amount) is not int or amount < 0:
            raise ValueError("invalid work observation")
        observed[metric] = observed.get(metric, 0) + amount

    def complete(receipts: Receipts) -> bool:
        return len(receipts) == len(names) and set(n for n, _ in receipts) == set(names)

    expected = tuple(oracle(case))
    if not complete(expected):
        raise ValueError("oracle does not cover the current scope inventory")
    actual = tuple(execute(case, charge))
    errors = []
    if not complete(actual) or dict(actual) != dict(expected):
        errors.append("incomplete or incorrect scope evidence")
    for metric, bound in bounds.items():
        if metric not in observed:
            errors.append(f"missing work observation: {metric}")
        elif observed[metric] > bound.limit(case):
            errors.append(f"{metric}: {observed[metric]} > {bound.limit(case)}")
    return errors


def check_matrix(cases: Sequence[Case], execute: Callable[[Case, Charge], Receipts],
                 oracle: Callable[[Case], Receipts], bounds: Mapping[str, Bound]) -> list[str]:
    """Run each owner-selected independent-scope/extent case exactly once."""
    if not cases:
        raise ValueError("expected a nonempty growth witness")
    return [f"case {i}: {error}" for i, case in enumerate(cases)
            for error in check_case(case, execute, oracle, bounds)]
