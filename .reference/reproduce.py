"""Compare actual committed dependency authority shapes, without installing."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from policy import source_errors

HEADS = {
    "all": "03de186a044c9c6b365347485a6c4093ce831c79",
    "fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
    "riverhog": "be483fd6d567616d5fcd355202d61f1e682efe75",
    "guavajam": "54fce07b619628a5e92be946be4b189873ddf1a0",
    "proffer": "2ce5e15c3191fcdc2be70213c0170f57c852a883",
    "forgejo-restic-restore-bootstrap": "5e64256f72a0baccfe85eed81d126d77b2fe59ab",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", type=Path, required=True)
    args = parser.parse_args()
    result = {}
    for name, expected in HEADS.items():
        root = args.repos / name
        assert subprocess.check_output(["git", "--no-replace-objects", "-C", str(root), "rev-parse", "HEAD"], text=True, env={**os.environ, "GIT_GRAFT_FILE": os.devnull}).strip() == expected
        assert not subprocess.check_output(["git", "--no-replace-objects", "-C", str(root), "status", "--porcelain", "--untracked-files=no"], text=True, env={**os.environ, "GIT_GRAFT_FILE": os.devnull})
        inputs = [p for p in ("requirements-dev.txt", "requirements-test.txt") if (root / p).is_file()]
        project = (root / "pyproject.toml").read_text() if (root / "pyproject.toml").is_file() else None
        lock = (root / "uv.lock").read_text() if (root / "uv.lock").is_file() else None
        result[name] = {"commit": expected, "pyproject": project is not None, "uv_lock": lock is not None, "authored_development_requirement_files": inputs, "source_shape_errors": source_errors(project, lock, inputs)}
    assert all(result[name]["source_shape_errors"] == [] for name in ("fishhat", "riverhog", "guavajam"))
    assert all(result[name]["source_shape_errors"] for name in ("all", "proffer", "forgejo-restic-restore-bootstrap"))
    print(json.dumps({"comparison": result, "limit": "Source shape only. No resolver freshness, actual command execution, dependency custody or migration qualification was run."}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
