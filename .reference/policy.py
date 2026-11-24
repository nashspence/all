"""Exercise complete owner workloads against an explicit affine work bound.

The owner supplies instrumentation and an independent result oracle. Finite
samples expose regressions; they do not prove asymptotic complexity or that the
owner counted every relevant operation. No elapsed-time threshold is involved.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, Any


def _integer(value: int, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"expected an integer >= {minimum}")
    return value


class Work:
    def __init__(self) -> None:
        self._total = 0
        self.recorded = False

    def charge(self, units: int = 1) -> None:
        self._total += _integer(units, 0)
        self.recorded = True

    @property
    def total(self) -> int:
        return self._total


@dataclass(frozen=True)
class Observation:
    extent: int
    work: int
    bound: int


def witness(
    extents: Iterable[int],
    workload: Callable[[int, Work], Any],
    expected: Callable[[int], Any],
    *,
    slope: int,
    intercept: int = 0,
) -> tuple[Observation, ...]:
    slope, intercept = _integer(slope, 1), _integer(intercept, 0)
    sizes = tuple(_integer(size, 1) for size in extents)
    if len(sizes) < 2 or any(a >= b for a, b in zip(sizes, sizes[1:])):
        raise ValueError("use at least two strictly increasing positive extents")
    observations = []
    for size in sizes:
        counter = Work()
        actual = workload(size, counter)
        if actual != expected(size):
            raise AssertionError(f"incorrect or incomplete result at extent {size}")
        if not counter.recorded:
            raise ValueError("required work observations are missing")
        bound = slope * size + intercept
        observation = Observation(size, counter.total, bound)
        observations.append(observation)
        if counter.total > bound:
            raise AssertionError(f"work bound exceeded: {observation}")
    return tuple(observations)
