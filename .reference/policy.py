"""Proposed shared Ruff formatting settings; validates declarations, not formatted source."""

import tomllib

PROFILE = {
    "line-length": 100,
    "indent-width": 4,
    "preview": False,
    "format.quote-style": "double",
    "format.indent-style": "space",
    "format.line-ending": "lf",
    "format.skip-magic-trailing-comma": False,
    "format.docstring-code-format": False,
    "format.preview": False,

}


def _equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return (all(isinstance(x, str) for x in actual)
                and len(set(actual)) == len(actual) and sorted(actual) == sorted(expected))
    return actual == expected


def settings_errors(settings, deviations=None):
    """A deviation binds one setting's actual value and a reviewable reason."""
    deviations = {} if deviations is None else deviations
    if not isinstance(settings, dict) or not isinstance(deviations, dict):
        return ["settings and deviations must be mappings"]
    errors = []
    for key in deviations:
        if key not in PROFILE:
            errors.append(f"unknown deviation: {key}")
    if "extend" in settings:
        errors.append("resolve shared settings explicitly in the root pyproject; no hidden extend")
    for key, expected in PROFILE.items():
        actual = settings
        for part in key.split("."):
            actual = actual.get(part) if isinstance(actual, dict) else None
        deviation = deviations.get(key)
        if _equal(actual, expected):
            if deviation is not None:
                errors.append(f"stale deviation: {key}")
            continue
        if (isinstance(deviation, dict) and set(deviation) == {"value", "reason"}
                and isinstance(deviation["reason"], str) and deviation["reason"].strip()
                and actual is not None and _equal(actual, deviation["value"])):
            continue
        errors.append(f"{key}: declare shared value {expected!r} or an exact reasoned deviation")
    return errors


def check_configs(files, deviations=None):
    """files is the complete maintained Ruff-config inventory, including pyprojects."""
    errors = []
    root = None
    for path, content in files.items():
        if path.split("/")[-1] not in {"pyproject.toml", "ruff.toml", ".ruff.toml"}:
            continue
        try:
            document = tomllib.loads(content)
        except (tomllib.TOMLDecodeError, TypeError) as exc:
            errors.append(f"{path}: invalid TOML: {exc}")
            continue
        tool = document.get("tool", {})
        if path.endswith("pyproject.toml") and not isinstance(tool, dict):
            errors.append(f"{path}: tool must be a table")
            continue
        settings = tool.get("ruff") if path.endswith("pyproject.toml") else document
        if path == "pyproject.toml":
            root = settings
        elif settings is not None:
            errors.append(f"{path}: a second Ruff authority can override the shared root profile")
    if root is None:
        errors.append("pyproject.toml: missing root tool.ruff profile")
    else:
        errors.extend(settings_errors(root, deviations))
    return errors
