import argparse
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path, PurePosixPath

from policy import layout_errors

HEADS = {
    "all": "03de186a044c9c6b365347485a6c4093ce831c79",
    "fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
    "riverhog": "be483fd6d567616d5fcd355202d61f1e682efe75",
    "guavajam": "54fce07b619628a5e92be946be4b189873ddf1a0",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=Path, required=True)
    args = parser.parse_args()
    results = {}
    for name, head in HEADS.items():
        repo = args.repos / name
        command = ["git", "--no-replace-objects", "-C", str(repo)]
        assert subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() == head
        assert not subprocess.check_output(command + ["status", "--porcelain", "--untracked-files=no"], text=True)
        tracked = subprocess.check_output(command + ["ls-tree", "-r", "--name-only", head], text=True).splitlines()
        projects = []
        for path in tracked:
            if PurePosixPath(path).name != "pyproject.toml":
                continue
            raw = subprocess.check_output(command + ["show", f"{head}:{path}"])
            metadata = tomllib.loads(raw.decode())
            if "project" not in metadata:
                continue
            parent = PurePosixPath(path).parent
            paths = {str(PurePosixPath(item).relative_to(parent)) for item in tracked if PurePosixPath(item).is_relative_to(parent)}
            errors = layout_errors(metadata, paths)
            projects.append({"path": path, "source_sha256": hashlib.sha256(raw).hexdigest(), "errors": errors, "needs_adapter": bool(errors) and all("adapter" in error for error in errors)})
        results[name] = {"commit": head, "projects": len(projects), "covered_canonical": sum(not x["errors"] for x in projects), "needs_adapter": sum(x["needs_adapter"] for x in projects), "layout_drift": sum(bool(x["errors"]) and not x["needs_adapter"] for x in projects), "details": projects}
    assert results["all"]["layout_drift"] == 1
    assert all(results[name]["layout_drift"] == 0 for name in ["fishhat", "riverhog", "guavajam"])
    assert results["riverhog"]["needs_adapter"] == 10
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
