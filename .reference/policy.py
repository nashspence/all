"""Compare actual example bytes with an owner-derived runtime projection."""
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def assert_example_parity(path, *, parse_example, runtime_projection):
    """Both callbacks return JSON-compatible semantic projections, not pass flags."""
    raw = Path(path).read_bytes()
    actual = parse_example(raw)
    expected = runtime_projection()
    if type(actual) is bool or type(expected) is bool:
        raise TypeError("semantic projections cannot be passed flags")
    if canonical(actual) != canonical(expected):
        raise AssertionError("checked-in example differs from its runtime authority")
    return actual
