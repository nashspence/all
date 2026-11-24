import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

from policy import repository_test_errors

SOURCES = {
    "fishhat": ("f96b83dc20f059d62a4363a63c37bb0ef8c642e5", ["tests/test_component_policy.py", "tests/test_repository_controls.py"]),
    "riverhog": ("be483fd6d567616d5fcd355202d61f1e682efe75", ["tests/unit/test_dependency_policy.py", "tests/unit/test_workspace_boundaries.py"]),
    "guavajam": ("54fce07b619628a5e92be946be4b189873ddf1a0", ["tests/repository/test_policy.py", "tests/repository/test_boundaries.py"]),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=Path, required=True)
    args = parser.parse_args()
    results = {}
    for name, (head, selected) in SOURCES.items():
        repo = args.repos / name
        command = ["git", "--no-replace-objects", "-C", str(repo)]
        assert subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() == head
        assert not subprocess.check_output(command + ["status", "--porcelain", "--untracked-files=no"], text=True)
        tracked = subprocess.check_output(command + ["ls-tree", "-r", "--name-only", head], text=True).splitlines()
        sources = {}
        for path in selected:
            raw = subprocess.check_output(command + ["show", f"{head}:{path}"])
            tree = ast.parse(raw)
            tests = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")]
            assert tests, path
            sources[path] = {"sha256": hashlib.sha256(raw).hexdigest(), "test_functions": len(tests)}
        results[name] = {"commit": head, "sources": sources, "errors": repository_test_errors(tracked, selected)}
    assert not results["guavajam"]["errors"]
    assert len(results["fishhat"]["errors"]) == 2
    assert len(results["riverhog"]["errors"]) == 2
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
