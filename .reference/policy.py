"""One location for classified repository-only maintenance source files."""

from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath


def script_errors(tracked: Iterable[str], repository_tools: Iterable[str], exceptions: Mapping[str, str] | None = None) -> list[str]:
    tracked = set(tracked)
    selected = list(repository_tools)
    exceptions = dict(exceptions or {})
    if len(set(selected)) != len(selected):
        raise ValueError("duplicate repository-tool classification")
    errors = []
    deviations = set()
    for path in selected:
        if not isinstance(path, str) or not path or "\\" in path or str(PurePosixPath(path)) != path or PurePosixPath(path).is_absolute() or {".", ".."}.intersection(path.split("/")):
            errors.append(f"noncanonical tool path: {path!r}")
            continue
        if path not in tracked:
            errors.append(f"classified tool is not tracked: {path}")
        elif not path.startswith("scripts/"):
            deviations.add(path)
            if path not in exceptions:
                errors.append(f"repository tool belongs under scripts/: {path}")
    for path, reason in exceptions.items():
        if path not in deviations:
            errors.append(f"stale or overbroad tool exception: {path}")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"tool exception requires a concrete retained constraint: {path}")
    return errors
