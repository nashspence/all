"""Compare owner-resolved artifact records; this does not parse or solve a lockfile."""

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Pin:
    name: str
    version: str
    sha256: frozenset[str]


@dataclass(frozen=True)
class Artifact:
    name: str
    version: str
    sha256: str


def _name(value: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", value):
        raise ValueError("invalid Python distribution name")
    return re.sub(r"[-_.]+", "-", value).lower()


def _hash(value: str) -> None:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("expected a canonical SHA-256 artifact digest")


def require_locked_subset(required: Iterable[Pin], selected: Iterable[Artifact]) -> None:
    """Every required pin resolves once to its version and an approved artifact hash.

    Selected records outside the required subset are intentionally outside this rule.
    The repository adapter decides whether required is its complete dependency closure.
    """
    pins = {}
    for pin in required:
        name = _name(pin.name)
        if name in pins:
            raise ValueError("duplicate normalized required distribution")
        if type(pin.version) is not str or not pin.version or not pin.sha256:
            raise ValueError("required pin lacks an exact version or artifact hashes")
        for digest in pin.sha256:
            _hash(digest)
        pins[name] = pin
    artifacts = {}
    for artifact in selected:
        name = _name(artifact.name)
        if name in artifacts:
            raise ValueError("duplicate normalized selected distribution")
        artifacts[name] = artifact
    for name, pin in pins.items():
        artifact = artifacts.get(name)
        if artifact is None:
            raise ValueError(f"required distribution was not resolved: {name}")
        _hash(artifact.sha256)
        if artifact.version != pin.version or artifact.sha256 not in pin.sha256:
            raise ValueError(f"resolved artifact differs from its owned pin: {name}")

