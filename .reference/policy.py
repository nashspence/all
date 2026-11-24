"""Measure one owner operation; optional speed goals never decide success.

The owner records observed work units and remains responsible for their meaning.
Exceptions from real execution or invalid required observations fail normally.
Cross-machine/reference comparison requires a separate owner profile adapter.
"""

from dataclasses import dataclass
import math
import time
from typing import Any, Callable


def _finite(value: float, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("a finite number is required")
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError("a finite number is required") from error
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError("a finite positive number is required" if positive else "a finite number is required")
    return value


class Work:
    def __init__(self) -> None:
        self.units: int | None = None

    def record(self, units: int) -> None:
        if type(units) is not int or units < 0:
            raise ValueError("observed work units must be nonnegative integers")
        self.units = (self.units or 0) + units


@dataclass(frozen=True)
class Observation:
    elapsed_seconds: float
    units: int
    unit: str
    rate_per_second: float | None
    goal_seconds: float | None
    goal_met: bool | None


def measure(
    operation: Callable[[Work], Any],
    *,
    unit: str,
    goal_seconds: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[Any, Observation]:
    if not isinstance(unit, str) or not unit:
        raise ValueError("the work unit is required")
    goal = None if goal_seconds is None else _finite(goal_seconds, positive=True)
    work = Work()
    start = _finite(clock())
    result = operation(work)
    elapsed = _finite(_finite(clock()) - start)
    if elapsed < 0:
        raise ValueError("measurement clock moved backwards")
    if work.units is None:
        raise ValueError("required observed work units are missing")
    rate = None if elapsed == 0 else _finite(work.units / elapsed)
    observation = Observation(
        elapsed, work.units, unit, rate, goal,
        None if goal is None else elapsed <= goal,
    )
    return result, observation
