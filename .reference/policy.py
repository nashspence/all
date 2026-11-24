"""Candidate versions for ordinary Python development, not public runtime support."""
from dataclasses import dataclass
import re
from typing import Iterable, Mapping


# Observed repository versions, offered as a seed; this does not qualify upgrades.
DEFAULT = {
    "python": "3.12.12",
    "uv": "0.11.24",
    "pytest": "9.1.1",
    "pytest-xdist": "3.8.0",
    "mypy": "2.4.0",
    "ruff": "0.17.1",
    "packaging": "26.3",
    "reuse": "6.3.0",
}


@dataclass(frozen=True)
class Deviation:
    version: str
    reason: str
    evidence: str
    revisit_when: str


def check_versions(
    observed: Mapping[str, str],
    enabled: Iterable[str],
    deviations: Mapping[str, Deviation] | None = None,
) -> list[str]:
    """Compare an adapter's complete ordinary-role tool inventory with one profile.

    ``enabled`` is derived from real development declarations, not hand-selected
    to omit inconvenient tools. Compatibility/native cohorts are separate inputs.
    A deviation records a decision; this checker cannot approve its rationale.
    """
    deviations = {} if deviations is None else deviations
    selected = set(enabled) | {"python", "uv"}
    errors = []
    unknown = (selected | set(observed) | set(deviations)) - set(DEFAULT)
    errors.extend(f"unknown profile tool: {name}" for name in sorted(unknown))
    errors.extend(f"unselected observed tool: {name}" for name in sorted(set(observed) - selected))
    for name in sorted(selected & set(DEFAULT)):
        actual = observed.get(name)
        deviation = deviations.get(name)
        version_shape = r"[0-9]+" + r"\.[0-9]+" * (len(DEFAULT[name].split(".")) - 1)
        if not isinstance(actual, str) or re.fullmatch(version_shape, actual) is None:
            errors.append(f"missing exact {name} version")
            continue
        if actual == DEFAULT[name]:
            if deviation is not None:
                errors.append(f"unused deviation: {name}")
            continue
        if deviation is None:
            errors.append(f"{name}: expected {DEFAULT[name]}, found {actual}")
        elif (
            deviation.version != actual
            or not deviation.reason.strip()
            or not deviation.evidence.startswith("https://")
            or not deviation.revisit_when.strip()
        ):
            errors.append(f"invalid or stale deviation: {name}")
    errors.extend(f"unused deviation: {name}" for name in sorted(set(deviations) - selected))
    return errors
