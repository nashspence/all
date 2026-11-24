"""Run default/help from a disposable tracked-file copy without project tools.

This checks observable filesystem changes inside the disposable workspace.
It is not a security sandbox for hostile Makefiles or absolute-path programs.
"""
import hashlib
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tempfile


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            payload = ("link", os.readlink(path))
        elif path.is_file():
            payload = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():
            payload = ("directory",)
        else:
            raise ValueError("unsupported workspace file type")
        result[name] = (stat.S_IMODE(info.st_mode), *payload)
    return result


def run(command, cwd, environment, timeout):
    process = subprocess.Popen(
        command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=(os.name == "posix"),
    )
    try:
        out, error = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.communicate()
        raise AssertionError("help timed out") from None
    if process.returncode:
        raise AssertionError(f"help failed with exit {process.returncode}: {error.strip()}")
    return out


def assert_fresh_help(root, *, required_text, make=None, base_utilities=("printf",), timeout=5):
    root = Path(root).resolve(strict=True)
    make = Path(make or shutil.which("make") or "").resolve(strict=True)
    if not make.is_file():
        raise ValueError("an existing make executable is required")
    names = subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=root)
    with tempfile.TemporaryDirectory(prefix="all-fresh-help-") as temporary:
        temporary = Path(temporary)
        checkout = temporary / "checkout"
        checkout.mkdir()
        for raw in names.split(b"\0"):
            if not raw:
                continue
            name = os.fsdecode(raw)
            source = root / name
            if not source.resolve(strict=True).is_relative_to(root):
                raise ValueError("tracked file escapes checkout")
            destination = checkout / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink() and not (destination.parent / os.readlink(source)).resolve().is_relative_to(checkout):
                raise ValueError("tracked symlink escapes disposable checkout")
            shutil.copy2(source, destination, follow_symlinks=False)
        for name in ("home", "config", "temporary", "base-utilities"):
            (temporary / name).mkdir()
        for name in base_utilities:
            if not name or Path(name).name != name:
                raise ValueError("base utilities must be exact command names")
            located = shutil.which(name)
            if not located or Path(located).resolve().is_relative_to(root):
                raise ValueError(f"base utility is unavailable outside the project: {name}")
            (temporary / "base-utilities" / name).symlink_to(Path(located).resolve())
        environment = {
            "PATH": str(temporary / "base-utilities"),
            "HOME": str(temporary / "home"),
            "XDG_CONFIG_HOME": str(temporary / "config"),
            "TMPDIR": str(temporary / "temporary"),
            "LC_ALL": "C",
        }
        before = snapshot(temporary)
        outputs = []
        for target in ([], ["help"]):
            outputs.append(run([str(make), "--no-print-directory", *target], checkout, environment, timeout))
            if snapshot(temporary) != before:
                raise AssertionError("help mutated its disposable workspace")
        if not outputs[0].strip() or outputs[0] != outputs[1]:
            raise AssertionError("default make and make help must show the same useful guidance")
        for text in required_text:
            if not text or text not in outputs[0]:
                raise AssertionError(f"missing owner-selected guidance: {text!r}")
        return outputs[0]
