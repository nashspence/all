import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from policy import facade_errors

HEADS = {
    "all": "03de186a044c9c6b365347485a6c4093ce831c79",
    "proffer": "2ce5e15c3191fcdc2be70213c0170f57c852a883",
    "forgejo-restic-restore-bootstrap": "5e64256f72a0baccfe85eed81d126d77b2fe59ab",
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
        raw = subprocess.run(["git", "--no-replace-objects", "-C", str(repo), "show", f"{head}:Makefile"], capture_output=True)
        assert raw.returncode == 0 or "Makefile" not in tracked
        source = raw.stdout.decode() if raw.returncode == 0 else None
        errors = facade_errors(source)
        results[name] = {"commit": head, "source_sha256": hashlib.sha256(raw.stdout).hexdigest() if source is not None else None, "errors": errors}
    assert not results["fishhat"]["errors"]
    assert not results["guavajam"]["errors"]
    assert all(results[name]["errors"] for name in ["all", "proffer", "forgejo-restic-restore-bootstrap", "riverhog"])
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
