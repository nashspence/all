"""Challenge an owner's declared optional observer/recovery boundary.

Every exercise gets fresh authoritative state. Optional observations cannot
change the expected authorized result or replace missing mandatory authority.
The owner supplies disposable fixtures and its real entrypoint adapter; this
does not declare arbitrary databases, acknowledgements or history optional.
"""

from copy import deepcopy
from typing import Any, Callable


def _unavailable() -> Any:
    raise OSError("optional observer unavailable")


def witness(
    operation: Callable[[Any, Callable[[], Any] | None], Any],
    *,
    authority: Callable[[], Any],
    missing_authority: Callable[[], Any],
    current_observation: Any,
    stale_observation: Any,
    expected: Any,
    refusal: type[Exception],
) -> None:
    if current_observation == stale_observation:
        raise ValueError("the stale observation must differ from the current one")
    observers = (
        ("present", lambda: deepcopy(current_observation)),
        ("absent", None),
        ("stale", lambda: deepcopy(stale_observation)),
        ("failing", _unavailable),
    )
    for name, observer in observers:
        actual = operation(authority(), observer)
        if actual != expected:
            raise AssertionError(f"optional {name} observation changed the authorized result")
        try:
            operation(missing_authority(), observer)
        except refusal:
            pass
        else:
            raise AssertionError(f"optional {name} observation substituted for mandatory authority")
