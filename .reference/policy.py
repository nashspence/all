"""Owner-defined flat public diagnostics and actual producer leakage regressions."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import re


def public_projection(raw, schema):
    """Schema values are exact bool/int types, finite enums, or fullmatch regexes."""
    if not schema:
        raise ValueError("owner diagnostic schema cannot be empty")
    result = {}
    for name, rule in schema.items():
        if name not in raw:
            raise ValueError(f"missing public diagnostic field: {name}")
        value = raw[name]
        if rule in (bool, int):
            valid = type(value) is rule
        elif isinstance(rule, (set, frozenset)) and all(type(item) is str for item in rule):
            valid = type(value) is str and value in rule
        elif isinstance(rule, re.Pattern):
            valid = type(value) is str and rule.fullmatch(value) is not None
        else:
            raise ValueError("unsupported owner diagnostic rule")
        if not valid:
            raise ValueError(f"invalid public diagnostic field: {name}")
        result[name] = value
    return result


def assert_secret_safe(produce, *, private_inputs, cases, schema):
    """Exercise produce(case, private_inputs), its record and Python stdout/stderr.

    This does not intercept arbitrary subprocess file descriptors or prove the
    absence of secrets that the owner did not inject into these real paths.
    """
    if not private_inputs or any(type(value) is not str or not value for value in private_inputs.values()):
        raise ValueError("nonempty injected private values are required")
    cases = list(cases)
    if not cases:
        raise ValueError("at least one actual producer case is required")
    forbidden = set(private_inputs.values())
    forbidden |= {json.dumps(value, ensure_ascii=True)[1:-1] for value in forbidden}
    results = []
    for case in cases:
        out, error = StringIO(), StringIO()
        result = None
        failure = None
        with redirect_stdout(out), redirect_stderr(error):
            try:
                result = produce(case, dict(private_inputs))
            except Exception as exc:
                failure = exc
        serialized = json.dumps(result, ensure_ascii=False, allow_nan=False)
        observed = "\n".join([out.getvalue(), error.getvalue(), serialized, str(failure or "")])
        if any(value in observed for value in forbidden):
            raise AssertionError("private input reached public diagnostics")
        if failure is not None:
            raise AssertionError("producer did not return its safe diagnostic record") from None
        if not isinstance(result, dict) or set(result) != set(schema):
            raise AssertionError("producer emitted fields outside its public diagnostic schema")
        public_projection(result, schema)
        results.append(result)
    return results
