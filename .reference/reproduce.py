"""Read actual development declarations and locked versions; do not run installs."""
import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

sys.dont_write_bytecode = True
from policy import DEFAULT, check_versions

HEADS = {
    "fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
    "riverhog": "be483fd6d567616d5fcd355202d61f1e682efe75",
    "guavajam": "54fce07b619628a5e92be946be4b189873ddf1a0",
    "forgejo-restic-restore-bootstrap": "5e64256f72a0baccfe85eed81d126d77b2fe59ab",
}


def normalized(requirement):
    match = re.match(r"[A-Za-z0-9_.-]+", requirement)
    return re.sub(r"[-_.]+", "-", match.group().lower()) if match else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", type=Path, required=True)
    args = parser.parse_args()
    result = {}
    for name, expected in HEADS.items():
        repo = args.repos / name
        assert subprocess.check_output(["git", "--no-replace-objects", "-C", str(repo), "rev-parse", "HEAD"], text=True, env={**os.environ, "GIT_GRAFT_FILE": os.devnull}).strip() == expected
        assert not subprocess.check_output(["git", "--no-replace-objects", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True, env={**os.environ, "GIT_GRAFT_FILE": os.devnull})
        observed = {}
        enabled = set()
        if (repo / "mise.toml").exists():
            tools = tomllib.loads((repo / "mise.toml").read_text())["tools"]
            observed.update({name: tools[name] for name in ("python", "uv") if name in tools})
        if (repo / "uv.lock").exists():
            manifest = tomllib.loads((repo / "pyproject.toml").read_text())
            for requirements in manifest.get("dependency-groups", {}).values():
                for requirement in requirements:
                    if isinstance(requirement, str) and normalized(requirement) in DEFAULT:
                        enabled.add(normalized(requirement))
            locked = tomllib.loads((repo / "uv.lock").read_text())["package"]
            for tool in enabled:
                versions = {package["version"] for package in locked if package["name"] == tool}
                assert len(versions) == 1, (name, tool, versions)
                observed[tool] = versions.pop()
        else:
            for requirement in (repo / "requirements-test.txt").read_text().splitlines():
                tool = normalized(requirement)
                if tool in DEFAULT:
                    enabled.add(tool)
                    observed[tool] = requirement.split("==", 1)[1].split()[0]
        result[name] = {"commit": expected, "ordinary_development_versions": observed, "candidate_profile_errors": check_versions(observed, enabled)}
    assert result["fishhat"]["ordinary_development_versions"]["python"] == "3.12.3"
    assert result["guavajam"]["ordinary_development_versions"]["python"] == "3.12.12"
    assert result["fishhat"]["ordinary_development_versions"]["ruff"] != result["riverhog"]["ordinary_development_versions"]["ruff"]
    assert result["forgejo-restic-restore-bootstrap"]["ordinary_development_versions"]["pytest"] == "8.3.5"
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
