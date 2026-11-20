import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
MODES = ("false", "input", "true")
ENV = {**os.environ, "GIT_ATTR_NOSYSTEM": "1"}

GUAVAJAM = (
    ":(glob)projects/core/src/guavajam_core/**/*.py",
    ":(glob)projects/core/src/guavajam_core/**/*.css",
    ":(glob)projects/view/src/guavajam/**/*.py",
    ":(glob)projects/view/src/guavajam/**/*.css",
)
XFAIL = {"guavajam": "https://github.com/nashspence/all/issues/1"}


def git(repo, *args):
    return subprocess.check_output(("git", "-C", str(repo), *args), env=ENV)


def tracked_paths(repo, selectors):
    paths = set()
    for selector in selectors:
        names = git(repo, "ls-files", "-z", "--", selector).split(b"\0")[:-1]
        if not names and not selector.endswith("/**/*.css"):
            raise SystemExit(f"{repo.name}: missing tracked inputs for {selector}")
        paths.update(os.fsdecode(name) for name in names)
    if not paths:
        raise SystemExit(f"{repo.name}: no tracked inputs")
    return sorted(paths)


def checkout_inputs(repo, paths, mode, destination):
    git(repo, "-c", f"core.autocrlf={mode}", "-c", "core.eol=lf",
        "-c", f"core.attributesFile={os.devnull}", "-c", "core.safecrlf=false",
        "checkout-index", f"--prefix={destination.as_posix()}/", "--", *paths)
    result = {}
    for path in paths:
        file = destination / path
        if file.is_symlink() or not file.is_file():
            raise SystemExit(f"{repo.name}: checkout did not produce a regular file: {path}")
        result[path] = file.read_bytes()
    return result


def check(name, selectors):
    repo = ROOT / "repos" / name
    if not (repo / ".git").exists():
        raise SystemExit(f"{name}: initialize the submodule first")
    paths = tracked_paths(repo, selectors)
    with TemporaryDirectory() as scratch:
        outputs = {
            mode: checkout_inputs(repo, paths, mode, Path(scratch) / mode)
            for mode in MODES
        }
    base = outputs["false"]
    if outputs["input"] != base:
        raise SystemExit(f"{name}: false and input checkouts differ")
    changed = [path for path in paths if outputs["true"][path] != base[path]]
    if not changed:
        if name in XFAIL:
            raise SystemExit(f"XPASS {name}: retire {XFAIL[name]}")
        print(f"PASS {name}: {len(paths)} exact-byte inputs")
        return
    if name not in XFAIL or any(
        outputs["true"][path].replace(b"\r\n", b"\n") != base[path]
        for path in changed
    ):
        raise SystemExit(f"FAIL {name}: byte drift in {', '.join(changed)}")
    print(f"XFAIL {name}: {len(changed)} inputs rewritten to CRLF; {XFAIL[name]}")


if __name__ == "__main__":
    check("guavajam", GUAVAJAM)
