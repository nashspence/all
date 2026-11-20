"""Check the pinned repositories' fresh-checkout GNU Make help entrypoint."""

import argparse
import os
import re
import selectors
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISSUE = "nashspence/all#11"
EXPECTED = {
    "0819870.xyz-public-keys": "missing Makefile",
    "forgejo-restic-restore-bootstrap": "missing Makefile",
    "press": "help needs installed publisher dependency",
    "proffer": "missing Makefile",
}
PRESS_ERROR = re.compile(
    r"Makefile:\d+: \*\*\* Install the locked dependency with make setup\.  Stop\."
)
PRESS_MISSING_MISE = {"make: mise: No such file or directory", "/bin/sh: 1: mise: not found"}


@dataclass(frozen=True)
class Pin:
    name: str
    path: Path
    commit: str


@dataclass(frozen=True)
class Failure:
    kind: str
    detail: str


def git(path, *args):
    return subprocess.check_output(("git", "-C", str(path), *args))


def tree(path, commit, *options):
    for record in git(path, "ls-tree", "-z", *options, commit).split(b"\0"):
        if record:
            metadata, name = record.split(b"\t", 1)
            mode, object_type, oid = metadata.split()
            yield mode, object_type, oid.decode(), name


def inventory(root):
    head = git(root, "rev-parse", "HEAD").decode().strip()
    yield Pin("all", root, head)
    for mode, _, commit, path in tree(root, head, "-r"):
        if mode != b"160000":
            continue
        if re.fullmatch(rb"repos/[a-z0-9][a-z0-9._-]*", path) is None or path == b"repos/all":
            raise ValueError(f"unexpected gitlink: {path!r}")
        child = root / path.decode()
        if not (child / ".git").exists() or git(child, "rev-parse", "HEAD").decode().strip() != commit:
            raise ValueError(f"{path.decode()} is not checked out at {commit}")
        yield Pin(child.name, child, commit)


def snapshot(pin, target):
    with tempfile.TemporaryFile() as data:
        subprocess.run(("git", "-C", str(pin.path), "archive", "--format=tar", pin.commit),
                       stdout=data, check=True)
        data.seek(0)
        with tarfile.open(fileobj=data, mode="r:") as archive:
            archive.extractall(target, filter="data")


def capture(cmd, timeout=20, limit=32_768):
    # Bound output before buffering it; Docker's memory limit doesn't cap its
    # client's stdout. Use a single deadline for both streams and process exit.
    deadline = time.monotonic() + timeout
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            buffers = {process.stdout: bytearray(), process.stderr: bytearray()}
            with selectors.DefaultSelector() as stream:
                for pipe in buffers:
                    stream.register(pipe, selectors.EVENT_READ)
                while stream.get_map():
                    remaining = deadline - time.monotonic()
                    events = stream.select(remaining) if remaining > 0 else []
                    if not events:
                        raise ValueError("GNU Make timed out")
                    for key, _ in events:
                        pipe = key.fileobj
                        chunk = os.read(pipe.fileno(), 4096)
                        if chunk:
                            buffers[pipe].extend(chunk)
                            if len(buffers[pipe]) > limit:
                                raise ValueError("GNU Make exceeded the output limit")
                        else:
                            stream.unregister(pipe)
            returncode = process.wait(timeout=max(0, deadline - time.monotonic()))
            stdout, stderr = (bytes(buf).decode(errors="replace") for buf in buffers.values())
            return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
        finally:
            if process.poll() is None:
                process.kill()


def run_make(image, directory, goal):
    name = f"make-help-{uuid.uuid4().hex}"
    cmd = (
        "docker", "run", "--rm", "--name", name, "--pull=never", "--network=none",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--user=65534:65534", "--pids-limit=64", "--memory=128m", "--log-driver=none",
        "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
        "--mount", f"type=bind,source={directory},target=/src,readonly",
        "--workdir=/src", "--env=HOME=/tmp", "--env=LC_ALL=C", "--entrypoint=make", image,
        *goal,
    )
    try:
        result = capture(cmd)
    except (ValueError, subprocess.TimeoutExpired) as exc:
        subprocess.run(("docker", "rm", "--force", name), capture_output=True,
                       timeout=10, check=False)
        raise ValueError(f"{exc} running {('make', *goal)}") from None
    if result.returncode in {125, 126, 127}:
        raise ValueError(f"Docker could not run GNU Make (exit {result.returncode}): {result.stderr[:400]!r}")
    return result


def press_setup_error(result):
    lines = result.stderr.strip().splitlines()
    return (
        result.returncode == 2 and not result.stdout.strip() and bool(lines)
        and PRESS_ERROR.fullmatch(lines[-1]) is not None
        and set(lines[:-1]) <= PRESS_MISSING_MISE
    )


def check_pin(pin, run):
    entries = {name: (mode, kind) for mode, kind, _, name in tree(pin.path, pin.commit)}
    makefile = entries.get(b"Makefile")
    if makefile is None:
        return Failure("missing Makefile", "no tracked root Makefile")
    if makefile not in {(b"100644", b"blob"), (b"100755", b"blob")}:
        return Failure("invalid Makefile", "tracked root Makefile must be a regular file")

    with tempfile.TemporaryDirectory(prefix="make-help-") as tmp:
        directory = Path(tmp) / "snapshot"
        directory.mkdir(mode=0o755)
        snapshot(pin, directory)
        if not (directory / "Makefile").is_file():
            return Failure("invalid Makefile", "tracked root Makefile missing from snapshot")
        bare, explicit = run(directory, ()), run(directory, ("help",))
    if press_setup_error(bare) and press_setup_error(explicit):
        return Failure("help needs installed publisher dependency",
                       "both help commands stop during publisher dependency loading")
    for title, result in (("make", bare), ("make help", explicit)):
        if result.returncode or not result.stdout.strip():
            return Failure("help failed", f"{title} must print guidance and exit zero "
                           f"(exit {result.returncode}, stdout={result.stdout[:300]!r}, "
                           f"stderr={result.stderr[:300]!r})")
    if bare.stdout.strip() != explicit.stdout.strip():
        return Failure("default differs", "make must show the same guidance as make help")
    return None


def check(pins, run, expected=EXPECTED):
    notes, errors = [], []
    seen = set()
    for pin in pins:
        seen.add(pin.name)
        failure = check_pin(pin, run)
        known = expected.get(pin.name)
        if not failure and known:
            errors.append(f"XPASS {pin.name} [{ISSUE}]; remove the resolved exception")
        elif failure and failure.kind == known:
            notes.append(f"XFAIL {pin.name}: {failure.detail} [{ISSUE}]")
        elif failure:
            errors.append(f"FAIL {pin.name}: {failure.detail}")
    errors.extend(f"FAIL {name}: stale exception for repository not pinned [{ISSUE}]"
                  for name in sorted(expected.keys() - seen))
    return notes, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="local Docker image with GNU Make and base shell utilities")
    args = parser.parse_args()
    try:
        pins = list(inventory(ROOT))
        notes, errors = check(pins, lambda directory, goal: run_make(args.image, directory, goal))
    except (ValueError, OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print(f"FAIL {str(exc)!r}", file=sys.stderr)
        return 1
    for note in notes:
        print(note)
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Checked {len(pins)} Make help entrypoints ({len(notes)} expected failures)")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
