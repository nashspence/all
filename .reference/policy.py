"""Validation-only incidental wait budgets; never a runtime timeout policy.

Owners explicitly select incidental sites and record the resolved scale. This
module reads no environment itself and changes no leases, semantic timeouts,
workloads, cleanup obligations or production deadlines.
"""

import math
import time
from typing import Callable


def _positive(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("a finite positive budget is required")
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError("a finite positive budget is required") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError("a finite positive budget is required")
    return value


def parse_scale(value: str | None) -> float:
    if value is None:
        return 1.0
    if not isinstance(value, str):
        raise ValueError("validation scale must be a string")
    return _positive(float(value))


class ValidationBudget:
    def __init__(
        self, nominal_seconds: float, scale: float = 1,
        *, clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.seconds = _positive(_positive(nominal_seconds) * _positive(scale))
        self._clock = clock
        self._start = self._read_clock()
        self._last = self._start

    def _read_clock(self) -> float:
        value = self._clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("the monotonic clock must return a finite number")
        try:
            value = float(value)
        except OverflowError as error:
            raise ValueError("the monotonic clock must return a finite number") from error
        if not math.isfinite(value):
            raise ValueError("the monotonic clock must return a finite number")
        return value

    def remaining(self) -> float:
        now = self._read_clock()
        if now < self._last:
            raise ValueError("the monotonic clock moved backwards")
        self._last = now
        remaining = self.seconds - (now - self._start)
        if remaining <= 0:
            raise TimeoutError("validation watchdog expired")
        return remaining

    def remaining_milliseconds(self) -> int:
        milliseconds = self.remaining() * 1000
        if not math.isfinite(milliseconds):
            raise ValueError("integer timeout conversion overflow")
        return math.ceil(milliseconds)
