"""Protect only owner-accepted baseline bytes; new files do not alter that promise."""

import hashlib
import re
import stat
from collections.abc import Mapping
from pathlib import Path, PurePosixPath


def check_protected_baseline(root: Path, expected_sha256: Mapping[str, str]) -> None:
    root = root.resolve(strict=True)
    for relative, expected in expected_sha256.items():
        path = PurePosixPath(relative)
        if (
            type(relative) is not str
            or not relative
            or "\\" in relative
            or path.is_absolute()
            or not path.parts
            or ".." in path.parts
            or str(path) != relative
        ):
            raise ValueError("baseline requires canonical relative file paths")
        if type(expected) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("baseline requires canonical SHA-256 digests")
        candidate = root
        try:
            for part in path.parts:
                candidate /= part
                if candidate.is_symlink():
                    raise ValueError("protected baseline cannot traverse symlinks")
            if not stat.S_ISREG(candidate.stat().st_mode):
                raise ValueError("protected baseline is not a regular file")
            observed = hashlib.sha256(candidate.read_bytes()).hexdigest()
        except OSError as error:
            raise ValueError(f"protected baseline is unavailable: {relative}") from error
        if observed != expected:
            raise ValueError(f"protected baseline bytes changed: {relative}")

