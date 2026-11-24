"""Inventory actual editor/check-out declarations; does not rewrite any source."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tomllib

sys.dont_write_bytecode = True
HEADS = {
    "riverhog": "be483fd6d567616d5fcd355202d61f1e682efe75",
    "fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
    "guavajam": "54fce07b619628a5e92be946be4b189873ddf1a0",
    "proffer": "2ce5e15c3191fcdc2be70213c0170f57c852a883",
    "all": "03de186a044c9c6b365347485a6c4093ce831c79",
    "forgejo-restic-restore-bootstrap": "5e64256f72a0baccfe85eed81d126d77b2fe59ab",
}

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True)


def sources(repos):
    for name, commit in HEADS.items():
        root = repos / name
        if git(root, "rev-parse", "HEAD").strip() != commit:
            raise SystemExit(f"{name}: wrong source commit")
        if git(root, "status", "--porcelain", "--untracked-files=all").strip():
            raise SystemExit(f"{name}: source checkout is not clean")
        paths = git(root, "ls-files").splitlines()
        yield name, root, paths


parser = argparse.ArgumentParser()
parser.add_argument("--repos", type=Path, required=True)
args = parser.parse_args()

from policy import check_config

observed = {}
for name, root, paths in sources(args.repos):
    content = git(root, "show", "HEAD:.editorconfig") if ".editorconfig" in paths else None
    nested = [p for p in paths if p.endswith("/.editorconfig")]
    attributes = git(root, "show", "HEAD:.gitattributes") if ".gitattributes" in paths else None
    observed[name] = {"editorconfig": content, "gitattributes": attributes,
                      "proposed_profile_errors": check_config(content, paths, nested_configs=nested)}
assert observed["guavajam"]["editorconfig"] is not None
assert all(observed[n]["editorconfig"] is None for n in HEADS if n != "guavajam")
assert observed["fishhat"]["gitattributes"].strip() == "* text=auto eol=lf"
assert "*.py text eol=lf" in observed["riverhog"]["gitattributes"]
print(json.dumps(observed, indent=2, sort_keys=True))
