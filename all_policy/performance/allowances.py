"""Design-owned absolute configuration envelopes, not marginal-cost claims.

The approved declaration supplies numbers and applicability. The reviewed
production verifier supplies activity facts; counts cannot prove their own
provenance or that a timed boundary includes all required work.
"""
import re

from .profiles import PROFILES

FEATURES = ("progress", "resumability", "logging")


def compile_limits(operation, profile, core_ns, optional_ns):
    """Derive core, applicable singletons and the supported all-on case.

    None means inapplicable; zero is applicable with no added headroom. The
    all-on case is deduplicated when there are fewer than two applicable features.
    Post-interruption recovery remains a separate ordinary operation and limit.
    """
    if not isinstance(operation, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,66}", operation):
        raise ValueError("operation must leave room for the canonical feature suffix")
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("use an existing shared profile")
    if type(core_ns) is not int or core_ns <= 0:
        raise ValueError("core requires positive integer nanoseconds")
    if not isinstance(optional_ns, dict) or set(optional_ns) != set(FEATURES):
        raise ValueError("consider progress, resumability and logging individually")
    if any(amount is not None and (type(amount) is not int or amount < 0)
           for amount in optional_ns.values()):
        raise ValueError("each applicable feature needs its own nonnegative allowance")
    active = tuple(feature for feature in FEATURES if optional_ns[feature] is not None)
    cases = [("core", ())] + [(feature, (feature,)) for feature in active]
    if len(active) > 1:
        cases.append(("all", active))
    selections, limits = {}, {}
    for suffix, features in cases:
        name = f"{operation}_{suffix}"
        selections[name] = features
        limits[name] = {"profile": profile,
                        "max_wall_ns": core_ns + sum(optional_ns[feature] for feature in features)}
    return {"schema": 1, "operations": limits}, selections


def require_activity(enabled, observed):
    """Check complete activity facts extracted by an approved production witness."""
    if (not isinstance(enabled, (list, tuple)) or
            any(not isinstance(feature, str) for feature in enabled) or
            len(set(enabled)) != len(enabled) or not set(enabled) <= set(FEATURES)):
        raise ValueError("unknown or repeated feature")
    if not isinstance(observed, dict) or set(observed) != set(FEATURES):
        raise ValueError("every feature needs an independent activity observation")
    for feature, count in observed.items():
        if type(count) is not int or count < 0:
            raise ValueError("activity requires nonnegative integer counts")
        if (count > 0) != (feature in enabled):
            raise ValueError("enabled feature was not exercised or disabled work occurred")


def validate_witness(enabled, witness):
    """Require correctness and feature activity, never self-declared timing credit."""
    if (not isinstance(witness, dict) or set(witness) != {"verified", "activity"}
            or witness["verified"] is not True):
        raise ValueError("approved verifier must report correctness and complete feature activity")
    require_activity(enabled, witness["activity"])
