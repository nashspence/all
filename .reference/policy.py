"""Run an exact-commit check in an exclusively owned Git checkout.

Boundary snapshots cannot detect an edit restored between snapshots. This is
source binding, not proof of test coverage or authorization. Git's normalization
rules remain separate from an exact checkout-byte policy.
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Sequence


class SourceError(ValueError):
    pass


@dataclass(frozen=True)
class Snapshot:
    commit: str
    status: bytes


@dataclass(frozen=True)
class Receipt:
    root: Path
    source: Snapshot
    command: tuple[str, ...]
    returncode: int


def snapshot(root: Path) -> Snapshot:
    root = root.resolve()

    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(root), *args])

    if Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
        raise SourceError("the check must own the repository root")
    tracked = git("ls-files", "-v", "-z").split(b"\0")
    if any(item and (item[:1].islower() or item[:1] == b"S") for item in tracked):
        raise SourceError("index flags must not hide source changes")
    return Snapshot(
        git("rev-parse", "--verify", "HEAD").decode().strip(),
        git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"),
    )


def _require_source(state: Snapshot, commit: str) -> None:
    if state.commit != commit or state.status:
        raise SourceError("qualification requires the named clean commit")


def run(root: Path, commit: str, command: Sequence[str]) -> Receipt:
    """Execute once; reject dirty, changed or failed qualification attempts."""
    if isinstance(command, (str, bytes)) or not command:
        raise ValueError("a nonempty argument vector is required")
    root = root.resolve()
    before = snapshot(root)
    _require_source(before, commit)
    completed = subprocess.run(tuple(command), cwd=root, check=False)
    after = snapshot(root)
    _require_source(after, commit)
    if after != before:
        raise SourceError("source changed during execution")
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, tuple(command))
    return Receipt(root, after, tuple(command), completed.returncode)


def require_current(receipt: Receipt) -> None:
    """Recheck before consuming this in-process receipt in a report."""
    if receipt.returncode != 0 or snapshot(receipt.root) != receipt.source:
        raise SourceError("execution evidence no longer matches current source")
    _require_source(receipt.source, receipt.source.commit)
