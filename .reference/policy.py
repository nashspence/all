"""Optional work controls; required product guarantees remain outside these switches."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar


FEATURES = frozenset({"progress", "resumability", "logging"})
T = TypeVar("T")


@dataclass(frozen=True)
class Controls:
    """One invocation's effective permissions, explicitly passed to its children."""

    enabled: frozenset[str] = FEATURES

    def __post_init__(self) -> None:
        if type(self.enabled) is not frozenset:
            raise TypeError("enabled must be an immutable feature set")
        if self.enabled - FEATURES:
            raise ValueError("unknown optional feature")

    @classmethod
    def all_off(cls) -> "Controls":
        return cls(frozenset())

    def without(self, *features: str) -> "Controls":
        disabled = frozenset(features)
        if disabled - FEATURES:
            raise ValueError("unknown optional feature")
        return Controls(self.enabled - disabled)

    def child(self, requested: "Controls") -> "Controls":
        """A child may narrow inherited permissions, never reopen them."""
        return Controls(self.enabled & requested.enabled)

    def call(self, feature: str, work: Callable[[], T]) -> T | None:
        """Gate the producer, including preparation; constructing work must be lazy."""
        if feature not in FEATURES:
            raise ValueError("unknown optional feature")
        if feature in self.enabled:
            return work()
        return None
