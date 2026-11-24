"""One candidate ordinary Python build profile, with exact qualified exceptions."""
from dataclasses import dataclass
import hashlib
from pathlib import PurePosixPath
from typing import Any, Mapping


DEFAULT = {"build-backend": "setuptools.build_meta", "requires": ["setuptools==84.2.1"]}


@dataclass(frozen=True)
class BuildException:
    build_system: Mapping[str, Any]
    witnesses: Mapping[str, str]
    reason: str
    evidence: str
    revisit_when: str


def relative_path(path: str) -> bool:
    value = PurePosixPath(path)
    return bool(path) and not value.is_absolute() and value.as_posix() == path and ".." not in value.parts and not any(character in path for character in "*?[\\")


def check_profiles(
    projects: Mapping[str, Mapping[str, Any]],
    tracked_files: Mapping[str, bytes],
    exceptions: Mapping[str, BuildException] | None = None,
) -> list[str]:
    """Check each discovered distribution's build-system table, not its artifacts.

    Exception evidence must be independently accepted before calling this checker;
    byte binding prevents an old decision silently covering a changed build hook.
    A build-system table remains in scope even with legacy setup.py/setup.cfg metadata.
    Virtual workspace roots without project or build-system tables are skipped.
    """
    exceptions = {} if exceptions is None else exceptions
    errors = []
    for path, manifest in projects.items():
        if not relative_path(path) or PurePosixPath(path).name != "pyproject.toml":
            errors.append(f"invalid project path: {path}")
            continue
        actual = manifest.get("build-system")
        exception = exceptions.get(path)
        if "project" not in manifest and "build-system" not in manifest:
            if exception is not None:
                errors.append(f"unused exception: {path}")
            continue
        if actual == DEFAULT:
            if exception is not None:
                errors.append(f"unused exception: {path}")
            continue
        if exception is None:
            errors.append(f"nonstandard ordinary build profile: {path}")
            continue
        valid = (
            exception.build_system == actual
            and bool(exception.witnesses)
            and bool(exception.reason.strip())
            and exception.evidence.startswith("https://")
            and bool(exception.revisit_when.strip())
        )
        for witness, digest in exception.witnesses.items():
            payload = tracked_files.get(witness)
            if not relative_path(witness) or payload is None or hashlib.sha256(payload).hexdigest() != digest:
                valid = False
        if not valid:
            errors.append(f"invalid or stale build exception: {path}")
    errors.extend(f"unused exception: {path}" for path in exceptions if path not in projects)
    return sorted(errors)
