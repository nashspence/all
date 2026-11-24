import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator


parser = argparse.ArgumentParser()
parser.add_argument("--repos", type=Path, required=True)
root = parser.parse_args().repos.resolve()
heads = {"proffer": "2ce5e15c3191fcdc2be70213c0170f57c852a883",
         "guavajam": "54fce07b619628a5e92be946be4b189873ddf1a0",
         "fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5"}
for name, commit in heads.items():
    assert subprocess.check_output(["git", "-C", str(root / name), "rev-parse", "HEAD"], text=True).strip() == commit
    subprocess.run(["git", "-C", str(root / name), "diff", "--quiet", "HEAD", "--"], check=True)
spec = importlib.util.spec_from_file_location("proffer_check", root / "proffer/check.py")
proffer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proffer)
record = json.loads((root / "proffer/tests/fixtures/handoff-edited.json").read_text())
record["source"]["base"]["commit"] += "\n"
assert proffer.errors(record) == []
sys.path.insert(0, str(root / "guavajam/src"))
from guavajam.catalog import CatalogError, validate
try:
    validate({"schema": "guavajam.catalog.v1", "hash_algorithm": "sha1",
              "tip": "a" * 40 + "\n", "editions": []})
except CatalogError:
    pass
else:
    raise AssertionError("expected Guavajam to reject the newline")
common = json.loads((root / "fishhat/packages/fishhat-contracts/src/fishhat_contracts/contracts/common.schema.json").read_text())
assert not Draft202012Validator(common["$defs"]["Digest"]).is_valid("sha256:" + "a" * 64 + "\n")
print(json.dumps({"proffer_commit_with_newline": "accepted",
                  "guavajam_commit_with_newline": "rejected",
                  "fishhat_digest_schema_with_newline": "rejected"}, sort_keys=True))
