"""Read actual source declarations; does not run the owner formatter or native suite."""

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
parser.add_argument("--ruff", type=Path, help="optional Ruff0.17.1 for the separate C901 cost probe")
args = parser.parse_args()

from policy import check_configs

observed = {}
for name, root, paths in sources(args.repos):
    files = {p: git(root, "show", f"HEAD:{p}") for p in paths
             if p.split("/")[-1] in {"pyproject.toml", "ruff.toml", ".ruff.toml"}}
    config = tomllib.loads(files.get("pyproject.toml", "")).get("tool", {}).get("ruff")
    observed[name] = {"declared_ruff": config, "proposed_profile_errors": check_configs(files)}
assert observed["riverhog"]["declared_ruff"]["line-length"] == 100
assert observed["fishhat"]["declared_ruff"]["line-length"] == 100
assert observed["riverhog"]["declared_ruff"]["lint"]["select"] != observed["fishhat"]["declared_ruff"]["lint"]["select"]
assert all(observed[n]["declared_ruff"] is None for n in ["guavajam", "proffer", "all", "forgejo-restic-restore-bootstrap"])
print(json.dumps(observed, indent=2, sort_keys=True))

if args.ruff:
    version = subprocess.check_output([str(args.ruff), "--version"], text=True).strip()
    if version != "ruff 0.17.1":
        raise SystemExit(f"unexpected probe tool: {version}")
    complexity = {}
    for name, target in [("riverhog", "py312"), ("fishhat", "py311")]:
        root = (args.repos / name).resolve()
        result = subprocess.run([str(args.ruff), "check", "--config", str(root / "pyproject.toml"),
            "--config", "lint.mccabe.max-complexity=20", "--no-cache", "--target-version", target,
            "--select", "C901", "--output-format", "json", str(root)], text=True, capture_output=True)
        if result.returncode not in (0, 1):
            raise SystemExit(result.stderr)
        complexity[name] = len(json.loads(result.stdout))
    assert complexity == {"riverhog": 154, "fishhat": 0}, complexity
    print(json.dumps({"separate_complexity_cost_probe": complexity, "tool": version}, sort_keys=True))
