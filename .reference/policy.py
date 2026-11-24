"""Owner-selected prose boundary; fixture exceptions execute their consumers."""
from pathlib import Path
import os
import subprocess

PROSE_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd", ".rst", ".adoc", ".asciidoc", ".txt"}


def contained_file(root, relative):
    root = Path(root).resolve(strict=True)
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(f"non-repository path: {relative}")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"not a contained file: {relative}")
    return resolved


def assert_prose_boundary(root, *, onboarding, legal=(), fixtures=None):
    """fixtures maps each data path to a callable that exercises its real bytes."""
    root = Path(root).resolve(strict=True)
    fixtures = {} if fixtures is None else fixtures
    groups = [set(onboarding), set(legal), set(fixtures)]
    if any(groups[a] & groups[b] for a in range(3) for b in range(a + 1, 3)):
        raise ValueError("prose classifications overlap")
    allowed = set().union(*groups)
    for relative in allowed:
        contained_file(root, relative)
        if Path(relative).suffix.lower() not in PROSE_SUFFIXES:
            raise ValueError(f"not a prose-like path: {relative}")
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    actual = {
        os.fsdecode(name) for name in raw.split(b"\0")
        if name and Path(os.fsdecode(name)).suffix.lower() in PROSE_SUFFIXES
    }
    if actual != allowed:
        raise AssertionError(f"prose inventory differs: extra={sorted(actual - allowed)}, missing={sorted(allowed - actual)}")
    for relative, consume in fixtures.items():
        consume(contained_file(root, relative))
