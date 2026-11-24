"""Compare discovered project owners with actual required-gate membership.

The local adapter reads canonical workspace roots and each tool's configuration
or collection. It selects applicable owners per invocation; this module does
not invent a second workspace registry or prescribe gate names.
"""

from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping


def discover(root: Path, workspace_roots: Iterable[str]) -> frozenset[str]:
    root = root.resolve()
    projects = set()
    for relative in workspace_roots:
        base = (root / relative).resolve()
        if not base.is_relative_to(root) or not base.is_dir():
            raise ValueError("workspace roots must be existing repository directories")
        for metadata in base.rglob("pyproject.toml"):
            resolved = metadata.resolve()
            if not resolved.is_relative_to(root):
                raise ValueError("project metadata escapes the repository")
            projects.add(resolved.parent.relative_to(root).as_posix())
    return frozenset(projects)


def require_coverage(projects: Iterable[str], gates: Mapping[str, Iterable[str]]) -> None:
    expected = frozenset(projects)
    if not expected or not gates:
        raise ValueError("explicit projects and required gates are necessary")
    problems = []
    for gate, members in gates.items():
        if isinstance(members, (str, bytes)):
            raise ValueError("gate membership must contain project identities")
        counts = Counter(members)
        missing = expected - counts.keys()
        extra = counts.keys() - expected
        duplicates = {name for name, count in counts.items() if count != 1}
        if missing or extra or duplicates:
            problems.append(
                f"{gate}: missing={sorted(missing)}, unknown={sorted(extra)}, "
                f"duplicate={sorted(duplicates)}"
            )
    if problems:
        raise ValueError("; ".join(problems))
