import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from policy import script_errors

HEADS = {
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
        raw = subprocess.check_output(command + ["ls-tree", "-r", "--name-only", head])
        tracked = raw.decode().splitlines()
        selected = [path for path in tracked if path.startswith(("scripts/", "tools/")) and path.endswith((".py", ".sh"))]
        results[name] = {"commit": head, "tracked_inventory_sha256": hashlib.sha256(raw).hexdigest(), "selected": selected, "count": len(selected), "errors": script_errors(tracked, selected)}
    assert not results["fishhat"]["errors"]
    assert not results["riverhog"]["errors"]
    assert len(results["guavajam"]["errors"]) == results["guavajam"]["count"] > 0
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
