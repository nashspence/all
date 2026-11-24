import os
from pathlib import PurePosixPath
import re
import subprocess


def _oid(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
        raise ValueError("expected a complete immutable Git object identity")
    return value


def _read(repo, *arguments):
    try:
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(repo), *arguments],
            env=os.environ | {"GIT_GRAFT_FILE": os.devnull},
            capture_output=True, check=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise ValueError("literal Git object read failed") from None
    return result.stdout


def commit_parents(repo, commit):
    _oid(commit)
    if _read(repo, "cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("expected an actual commit object")
    raw = _read(repo, "cat-file", "commit", commit)
    header = raw.split(b"\n\n", 1)[0]
    return tuple(_oid(line[7:].decode("ascii")) for line in header.splitlines() if line.startswith(b"parent "))


def blob_bytes(repo, commit, path, *, maximum_bytes):
    _oid(commit)
    relative = PurePosixPath(path)
    if not path or str(relative) != path or relative.is_absolute() or ".." in relative.parts or "\\" in path or "\x00" in path:
        raise ValueError("expected a canonical relative Git path")
    if type(maximum_bytes) is not int or maximum_bytes < 0:
        raise ValueError("owner must supply a nonnegative byte budget")
    if _read(repo, "cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("expected an actual commit object")
    target = commit + ":" + path
    size = int(_read(repo, "cat-file", "-s", target))
    if size > maximum_bytes:
        raise ValueError("blob exceeds the owner's byte budget")
    raw = _read(repo, "cat-file", "blob", target)
    if len(raw) != size:
        raise ValueError("literal blob size changed")
    return raw
