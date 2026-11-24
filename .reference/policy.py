"""Resolve actual Python patch identity and compare owner-selected runtime records."""

import json
import subprocess
from collections.abc import Mapping


def python_identity(executable: str) -> dict[str, str]:
    command = (
        "import json,platform,sys; "
        "print(json.dumps({'python.implementation': sys.implementation.name, "
        "'python.version': platform.python_version(), "
        "'python.cache_tag': sys.implementation.cache_tag}))"
    )
    result = subprocess.run([executable, "-I", "-c", command], check=True, capture_output=True, text=True)
    identity = json.loads(result.stdout)
    _validate(identity)
    return identity


def _validate(identity: Mapping[str, str]) -> None:
    if not identity or any(type(key) is not str or not key or type(value) is not str or not value for key, value in identity.items()):
        raise ValueError("runtime identities require nonempty string fields")


def require_runtime_cohort(expected: Mapping[str, str], fragments: Mapping[str, Mapping[str, str]]) -> None:
    """Compare exact fields selected by the owner; separate profiles form separate cohorts."""
    _validate(expected)
    if not fragments:
        raise ValueError("runtime cohort has no execution fragments")
    for fragment, identity in fragments.items():
        if type(fragment) is not str or not fragment:
            raise ValueError("execution fragment requires an identity")
        _validate(identity)
        if dict(identity) != dict(expected):
            raise ValueError(f"execution fragment runtime differs from resolved cohort: {fragment}")

