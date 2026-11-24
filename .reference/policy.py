"""Check complete logical results across an owner-provided paging boundary.

This is a finite test witness, not a production paginator or resource policy.
The owner supplies independent expected identities, real cursor semantics and
retry behavior. Cycles are rejected; termination of endlessly fresh empty
cursors requires the owner's separate liveness/watchdog contract.
"""

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class Page:
    identities: tuple[str, ...]
    next_cursor: str | None


def _identity(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("logical identities and nonterminal cursors must be nonempty strings")
    return value


def require_complete(
    expected: Iterable[str], fetch: Callable[[str | None], Page]
) -> int:
    if isinstance(expected, (str, bytes)):
        raise ValueError("expected must contain logical identities")
    identities = tuple(_identity(item) for item in expected)
    wanted = set(identities)
    if len(wanted) != len(identities):
        raise ValueError("the independent expected inventory contains duplicates")
    seen: set[str] = set()
    cursors: set[str] = set()
    cursor = None
    while True:
        page = fetch(cursor)
        for item in page.identities:
            item = _identity(item)
            if item not in wanted or item in seen:
                raise AssertionError(f"unexpected or repeated logical identity: {item}")
            seen.add(item)
        cursor = page.next_cursor
        if cursor is None:
            break
        cursor = _identity(cursor)
        if cursor in cursors:
            raise AssertionError("paging cursor cycle")
        cursors.add(cursor)
    if seen != wanted:
        raise AssertionError(f"incomplete logical result: {len(wanted - seen)} identities missing")
    return len(seen)
