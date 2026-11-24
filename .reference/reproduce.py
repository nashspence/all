import argparse
import json
from pathlib import Path
import subprocess

import yaml

from policy import missing_updates, surfaces


HEADS = {
    "riverhog": "be483fd6d567616d5fcd355202d61f1e682efe75",
    "fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
    "guavajam": "54fce07b619628a5e92be946be4b189873ddf1a0",
    "all": "03de186a044c9c6b365347485a6c4093ce831c79",
    "proffer": "2ce5e15c3191fcdc2be70213c0170f57c852a883",
    "forgejo-restic-restore-bootstrap": "5e64256f72a0baccfe85eed81d126d77b2fe59ab",
    "0819870.xyz-public-keys": "714d90e5a2de382355e76b6399ecd50b4d6044e2",
}


def compare(repositories):
    rows = []
    for name, expected in HEADS.items():
        root = repositories / name
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)
        if head != expected or status:
            raise ValueError(f"{name}: inspect the recorded source commit")
        paths = subprocess.check_output(["git", "-C", str(root), "ls-files"], text=True).splitlines()
        path = root / ".github/dependabot.yml"
        config = yaml.safe_load(path.read_text()) if path.exists() else None
        rows.append({"repository": name, "commit": head, "surfaces": sorted(surfaces(paths)),
                     "missing_routes": missing_updates(paths, config)})
    expected_counts = {"riverhog": 0, "fishhat": 0, "guavajam": 4, "all": 1,
                       "proffer": 1, "forgejo-restic-restore-bootstrap": 1, "0819870.xyz-public-keys": 0}
    for row in rows:
        if len(row["missing_routes"]) != expected_counts[row["repository"]]:
            raise AssertionError(row)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare exact recorded repository checkouts without modifying them.")
    parser.add_argument("--repos", dest="repositories", type=Path, required=True, help="directory containing the seven named Git checkouts")
    print(json.dumps(compare(parser.parse_args().repositories.resolve()), indent=2))
