"""Exact owned-file cleanup for disposable qualification directories.

This filesystem adapter does not delete directories, follow symlinks, infer
ownership from prefixes, or claim hostile concurrent-filesystem protection.
"""
from dataclasses import dataclass
from hashlib import sha256
import hmac
import os
from pathlib import Path
import secrets
import stat

MARKER = ".qualification-owner"


@dataclass(frozen=True)
class FileClaim:
    relative: str
    token: str
    device: int
    inode: int
    sha256: str


def checked_root(root, token):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("cleanup root must be an actual directory")
    root = root.resolve(strict=True)
    marker = root / MARKER
    if not stat.S_ISREG(marker.lstat().st_mode) or not hmac.compare_digest(marker.read_text(), token):
        raise ValueError("ownership token differs")
    return root


def contained(root, relative):
    if not isinstance(relative, str):
        raise ValueError("owned resource path must be a canonical relative string")
    value = Path(relative)
    if value.as_posix() != relative or value.is_absolute() or ".." in value.parts or value.as_posix() == MARKER:
        raise ValueError("invalid owned resource path")
    path = root / value
    if path == root or not path.resolve().is_relative_to(root):
        raise ValueError("resource escapes owned directory")
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError("owned paths cannot traverse symlinks")
        current = current.parent
    return path


def claim_empty_directory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
        raise ValueError("claim requires an empty actual directory")
    token = secrets.token_hex(32)
    descriptor = os.open(root / MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as out:
        out.write(token)
    return token


def create_owned_file(root, token, relative, data):
    root = checked_root(root, token)
    path = contained(root, relative)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as out:
        out.write(data)
        info = os.fstat(out.fileno())
    return FileClaim(relative, token, info.st_dev, info.st_ino, sha256(data).hexdigest())


def cleanup_owned_files(root, token, claims):
    root = checked_root(root, token)
    claims = list(claims)
    paths = []
    seen = set()
    for claim in claims:
        if not hmac.compare_digest(claim.token, token):
            raise ValueError("resource belongs to another run")
        path = contained(root, claim.relative)
        resolved = path.resolve(strict=True)
        if resolved in seen:
            raise ValueError("duplicate normalized cleanup path")
        seen.add(resolved)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (claim.device, claim.inode):
            raise ValueError("owned file identity changed")
        if sha256(path.read_bytes()).hexdigest() != claim.sha256:
            raise ValueError("owned file bytes changed")
        paths.append(path)
    # Preflight every selected identity before deleting any selected file.
    checked_root(root, token)
    for path in paths:
        path.unlink()
    return len(paths)
