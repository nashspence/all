"""Witness nonmutating schema admission inside an owned fixture tree.

This observes net tree changes, not transient effects or writes outside that tree.
The callback is the owner's admission/open operation, not its normal write workload.
"""

import hashlib
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class StateIdentity:
    owner: str
    schema: str

    def __post_init__(self) -> None:
        if any(type(value) is not str or not value for value in (self.owner, self.schema)):
            raise ValueError("state identity fields must be nonempty strings")


def require_state_identity(actual: StateIdentity, expected: StateIdentity) -> None:
    if actual != expected:
        raise ValueError("existing state has an unexpected owner or schema")


def _snapshot(root: Path) -> dict[str, tuple]:
    if not root.exists() and not root.is_symlink():
        return {".": ("missing",)}
    paths = [root]
    for directory, directories, files in os.walk(root, followlinks=False):
        paths.extend(Path(directory) / name for name in directories + files)
    result = {}
    for path in paths:
        status = path.lstat()
        if stat.S_ISLNK(status.st_mode):
            raise ValueError("schema-admission fixture must not contain symlinks")
        metadata = (status.st_mode, status.st_size, status.st_mtime_ns)
        if stat.S_ISREG(status.st_mode):
            data = ("file", *metadata, hashlib.sha256(path.read_bytes()).digest())
        elif stat.S_ISDIR(status.st_mode):
            data = ("directory", *metadata)
        else:
            raise ValueError("schema-admission fixture contains a special file")
        result[path.relative_to(root).as_posix()] = data
    return result


def unchanged_open(root: Path, open_existing: Callable[[], T]) -> T:
    before = _snapshot(root)
    try:
        return open_existing()
    finally:
        if _snapshot(root) != before:
            raise AssertionError("schema admission changed the existing state tree")

