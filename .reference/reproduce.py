"""Compare committed configuration; never execute a consumer workflow."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

HEADS = {
    "all": "03de186a044c9c6b365347485a6c4093ce831c79",
    "fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
    "riverhog": "be483fd6d567616d5fcd355202d61f1e682efe75",
    "guavajam": "54fce07b619628a5e92be946be4b189873ddf1a0",
    "proffer": "2ce5e15c3191fcdc2be70213c0170f57c852a883",
    "forgejo-restic-restore-bootstrap": "5e64256f72a0baccfe85eed81d126d77b2fe59ab",
}
PRIMARY = {name: ".github/workflows/" + filename for name, filename in {
    "all": "test.yml", "fishhat": "ci.yml", "riverhog": "ci.yml",
    "guavajam": "ci.yml", "proffer": "test.yml",
    "forgejo-restic-restore-bootstrap": "tests.yml",
}.items()}


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_GRAFT_FILE"] = os.devnull
    return subprocess.check_output(
        ["git", "--no-replace-objects", "-c", "advice.graftFileDeprecated=false", "-C", str(repo), *args],
        text=True, env=env)


def sources(root, name):
    repo = root / name
    sha = HEADS[name]
    if git(repo, "rev-parse", "HEAD").strip() != sha:
        raise RuntimeError(f"{name}: expected source {sha}")
    if git(repo, "status", "--porcelain", "--untracked-files=all").strip():
        raise RuntimeError(f"{name}: expected a clean checkout")
    paths = git(repo, "ls-tree", "-r", "--name-only", sha).splitlines()
    return {p: git(repo, "show", f"{sha}:{p}") for p in paths
            if p.startswith(".github/") and p.endswith((".yml", ".yaml"))}


def args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=Path, required=True)
    return parser.parse_args()

from policy import CATALOG, check_workflows, references

if __name__ == "__main__":
    root = args().repos
    result = {}
    for name in HEADS:
        files = {p: t for p, t in sources(root, name).items()
                 if p.startswith(".github/workflows/")}
        observed = {}
        for path, text in files.items():
            for ref in references(path, text).values():
                action, _, revision = ref.partition("@")
                if action in CATALOG:
                    observed.setdefault(action, set()).add(revision)
        result[name] = {"observed": {k: sorted(v) for k, v in observed.items()},
                        "problems": check_workflows(files)}
    assert not result["riverhog"]["problems"]
    assert all(result[n]["problems"] for n in HEADS if n != "riverhog")
    print(json.dumps(result, indent=2))
