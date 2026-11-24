import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


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
sys.path[:0] = [str(root / "fishhat/packages/fishhat-contracts/src"), str(root / "guavajam/src")]
from fishhat_contracts.validation import FORMAT_CHECKER, validate
from guavajam.catalog import CatalogError, https
assert "uri" not in proffer.VALIDATOR.format_checker.checkers, "URI extra is installed; use the declared base dependency environment"
assert "uri" not in FORMAT_CHECKER.checkers, "URI extra is installed; use the declared base dependency environment"
invalid = "https://example.invalid/a b"
record = json.loads((root / "proffer/tests/fixtures/handoff-edited.json").read_text())
record["issue"] = invalid
assert proffer.errors(record) == []
validate("common.schema.json", {"uri": invalid, "digest": "sha256:" + "a" * 64}, "SchemaIdentity")
try:
    https(invalid, "issue URL")
except CatalogError:
    pass
else:
    raise AssertionError("expected Guavajam to reject whitespace in the URI")
print(json.dumps({"uri_checker_available": False, "proffer_invalid_issue_url": "accepted",
                  "fishhat_invalid_schema_uri": "accepted", "guavajam_invalid_https_url": "rejected"}, sort_keys=True))
