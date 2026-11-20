import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=ROOT):
    return subprocess.check_output(("git", *args), cwd=cwd, text=True).rstrip("\n")


def check(checkout):
    modules = {}
    for entry in git("config", "--null", "--file", ".gitmodules", "--list").split("\0"):
        if not entry:
            continue
        key, value = entry.split("\n", 1)
        match = re.fullmatch(r"submodule\.([a-z0-9][a-z0-9._-]*)\.(path|url)", key)
        if not match:
            raise SystemExit(f"Unexpected submodule setting: {key}")
        name, field = match.groups()
        expected = f"repos/{name}" if field == "path" else f"https://github.com/nashspence/{name}.git"
        if name == "all" or value != expected or field in modules.setdefault(name, {}):
            raise SystemExit(f"Invalid submodule setting: {key}")
        modules[name][field] = value

    if not modules or any(set(module) != {"path", "url"} for module in modules.values()):
        raise SystemExit("Each submodule needs one path and one URL")
    paths = {f"repos/{name}" for name in modules}
    pins = {}
    for record in git("ls-files", "--stage", "-z").split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, sha, stage = metadata.split()
        if mode == "160000":
            if stage != "0":
                raise SystemExit(f"Unmerged gitlink: {path}")
            pins[path] = sha
    if paths != pins.keys():
        raise SystemExit(f"Gitlinks differ from .gitmodules: {sorted(paths ^ pins.keys())}")

    if checkout:
        for path, sha in sorted(pins.items()):
            child = ROOT / path
            if (not (child / ".git").exists()
                    or git("rev-parse", "HEAD", cwd=child) != sha):
                raise SystemExit(f"{path} is not checked out at {sha}")
    print(f"Verified {len(pins)} submodule pins" + (" and checkouts" if checkout else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", action="store_true")
    check(parser.parse_args().checkout)
