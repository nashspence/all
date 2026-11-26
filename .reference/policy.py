"""Compile approved normal-operation allowances into the existing raw-time schema.

These are configuration envelopes, not measurements of marginal feature cost.
Classification, approval and complete production bindings remain owner duties.
"""

import re

from all_policy.performance.profiles import PROFILES

FEATURES = ("progress", "resumability", "logging")


def compile_limits(operation, profile, core_ns, optional_ns):
    """Return limits and the exact feature selection required of each binding.

    All three features must be considered; None explicitly means inapplicable.
    Zero keeps a feature applicable while granting no additional headroom.
    Recovery after failure is a separate operation, not the normal-work allowance.
    """
    if not isinstance(operation, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,66}", operation):
        raise ValueError("operation must leave room for the canonical feature suffix")
    if profile not in PROFILES:
        raise ValueError("use an existing shared profile")
    if type(core_ns) is not int or core_ns <= 0:
        raise ValueError("core requires positive integer nanoseconds")
    if set(optional_ns) != set(FEATURES):
        raise ValueError("consider progress, resumability and logging individually")
    for amount in optional_ns.values():
        if amount is not None and (type(amount) is not int or amount < 0):
            raise ValueError("each applicable feature needs its own nonnegative allowance")

    active = tuple(feature for feature in FEATURES if optional_ns[feature] is not None)
    cases = [("core", ())] + [(feature, (feature,)) for feature in active]
    if len(active) > 1:
        cases.append(("all", active))
    selections, limits = {}, {}
    for suffix, features in cases:
        name = f"{operation}_{suffix}"
        selections[name] = features
        limits[name] = {
            "profile": profile,
            "max_wall_ns": core_ns + sum(optional_ns[feature] for feature in features),
        }
    return {"schema": 1, "operations": limits}, selections


def require_selections(expected, bound):
    """Compare with selections extracted from reviewed real-operation bindings."""
    if bound != expected:
        raise ValueError("missing, extra or incorrectly configured canonical case")


def require_activity(enabled, independently_observed):
    """For an approved verifier: actual feature events, never claimed enable flags.

    The verifier owns what constitutes a completed feature event and must cover
    the timed operation. Counts alone cannot establish provenance or completeness.
    """
    if len(set(enabled)) != len(enabled) or not set(enabled) <= set(FEATURES):
        raise ValueError("unknown or repeated feature")
    if set(independently_observed) != set(FEATURES):
        raise ValueError("every feature needs an independent activity observation")
    for feature, count in independently_observed.items():
        if type(count) is not int or count < 0:
            raise ValueError("activity requires nonnegative integer counts")
        if (count > 0) != (feature in enabled):
            raise ValueError("enabled feature was not exercised or disabled work occurred")
