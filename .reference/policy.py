"""One discoverable home for classified Python repository-only policy tests."""

from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath


def repository_test_errors(tracked: Iterable[str], repository_tests: Iterable[str], exceptions: Mapping[str, str] | None = None) -> list[str]:
    tracked = set(tracked)
    selected = list(repository_tests)
    exceptions = dict(exceptions or {})
    if len(set(selected)) != len(selected):
        raise ValueError("duplicate repository-test classification")
    errors, deviations = [], set()
    for path in selected:
        if not isinstance(path, str) or not path or "\\" in path or str(PurePosixPath(path)) != path or PurePosixPath(path).is_absolute() or {".", ".."}.intersection(path.split("/")):
            errors.append(f"noncanonical repository-test path: {path!r}")
            continue
        if path not in tracked:
            errors.append(f"classified repository test is not tracked: {path}")
            continue
        name = PurePosixPath(path).name
        if not path.startswith("tests/repository/") or not name.startswith("test_") or not name.endswith(".py"):
            deviations.add(path)
            if path not in exceptions:
                errors.append(f"repository-only Python test belongs at tests/repository/**/test_*.py: {path}")
    for path, reason in exceptions.items():
        if path not in deviations:
            errors.append(f"stale or overbroad repository-test exception: {path}")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"repository-test exception requires a concrete retained constraint: {path}")
    return errors
