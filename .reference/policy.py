"""A common root for retained developer evidence, preserving owner subpaths."""

from collections.abc import Mapping
from pathlib import PurePosixPath


def evidence_output_errors(defaults: Mapping[str, str], exceptions: Mapping[str, dict[str, str]] | None = None) -> list[str]:
    exceptions = dict(exceptions or {})
    errors, deviations = [], set()
    for owner, path in defaults.items():
        if not isinstance(owner, str) or not owner.strip():
            errors.append("evidence producer needs a current owned identity")
        if not isinstance(path, str) or not path or "\\" in path or str(PurePosixPath(path)) != path or PurePosixPath(path).is_absolute() or {".", ".."}.intersection(path.split("/")):
            errors.append(f"{owner}: output default must be a canonical checkout-relative path")
            continue
        if path != "artifacts" and not path.startswith("artifacts/"):
            deviations.add(owner)
            exception = exceptions.get(owner)
            if not isinstance(exception, dict) or set(exception) != {"path", "reason"} or exception.get("path") != path or not isinstance(exception.get("reason"), str) or not exception["reason"].strip():
                errors.append(f"{owner}: retained developer evidence belongs under artifacts/: {path}")
    for owner in exceptions:
        if owner not in deviations:
            errors.append(f"{owner}: stale or unknown evidence-output exception")
    return errors
