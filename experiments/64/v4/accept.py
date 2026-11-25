"""Raw elapsed-time acceptance; callers load authority from a trusted revision.

The trusted outer timer supplies samples_ns. The operation adapter supplies no
timing, budget, profile, calibration factor, or acceptance decision. Admission is
{profile_id: bool}; it comes from the independent preflight environment check.
"""
from collections.abc import Mapping


def evaluate(operation_id, samples_ns, admission, contract, candidate_claims=None):
    """Return a decision without modifying authority, samples, or admission.

    Invalid evidence never passes. Candidate claims are rejected, not merged.
    Min/mean are diagnostics; all three raw samples must meet the fixed budget.
    """
    claims = sorted(str(key) for key in candidate_claims) if isinstance(candidate_claims, Mapping) else (["invalid_claims_container"] if candidate_claims is not None else [])
    result = {
        "operation_id": operation_id, "verdict": "invalid_evidence",
        "budget_ns": None, "profile": None, "sample_count": None,
        "raw_min_ns": None, "raw_max_ns": None, "raw_mean_ns": None,
        "over_budget_indices": [], "claims_rejected": claims,
        "candidate_claims_effect": "none", "error": None,
    }
    if not isinstance(contract, Mapping) or contract.get("repetitions") != 3:
        result["error"] = "invalid_contract"
        return result
    operations = contract.get("operations")
    if not isinstance(operation_id, str) or not isinstance(operations, Mapping) or operation_id not in operations:
        result["error"] = "unknown_operation"
        return result
    specification = operations[operation_id]
    if not isinstance(specification, Mapping):
        result["error"] = "invalid_contract"
        return result
    budget, profile = specification.get("budget_ns"), specification.get("profile")
    if type(budget) is not int or budget <= 0 or not isinstance(profile, str) or not profile:
        result["error"] = "invalid_contract"
        return result
    result.update(budget_ns=budget, profile=profile)
    if not isinstance(samples_ns, (list, tuple)):
        result["error"] = "invalid_samples_container"
        return result
    result["sample_count"] = len(samples_ns)
    if len(samples_ns) != 3:
        result["error"] = "incomplete_observations"
        return result
    if any(type(value) is not int or value <= 0 for value in samples_ns):
        result["error"] = "nonpositive_or_invalid_duration"
        return result
    over = [index for index, value in enumerate(samples_ns) if value > budget]
    result.update(raw_min_ns=min(samples_ns), raw_max_ns=max(samples_ns),
                  raw_mean_ns=sum(samples_ns) / 3, over_budget_indices=over)
    if not isinstance(admission, Mapping) or admission.get(profile) is not True:
        result["verdict"] = "unqualified"
    elif not over:
        result["verdict"] = "pass"
    else:
        result["verdict"] = "all_over" if len(over) == 3 else "mixed_miss"
    return result
