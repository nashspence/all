import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

from policy import evidence_output_errors

SOURCES = {
    "fishhat": ("f96b83dc20f059d62a4363a63c37bb0ef8c642e5", {
        "scripts/validation.py": ["artifacts/validation"],
        "scripts/validation_pytest.py": ["artifacts/test-stats"],
        "scripts/profile.py": ["artifacts/profiles"],
    }),
    "riverhog": ("be483fd6d567616d5fcd355202d61f1e682efe75", {
        "scripts/ci_make.py": ["build/ci-timing"],
        "scripts/ci_timing.py": ["build/ci-timing"],
        "scripts/transfer_profile.py": ["build/publication-profile", "build/stove0-scale-profile"],
    }),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=Path, required=True)
    args = parser.parse_args()
    results = {}
    for name, (head, sources) in SOURCES.items():
        command = ["git", "--no-replace-objects", "-C", str(args.repos / name)]
        assert subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() == head
        assert not subprocess.check_output(command + ["status", "--porcelain", "--untracked-files=no"], text=True)
        defaults, records = {}, {}
        for path, selected in sources.items():
            raw = subprocess.check_output(command + ["show", f"{head}:{path}"])
            tree = ast.parse(raw)
            values = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
            assert set(selected) <= values, path
            for output in selected:
                defaults[path + ":" + output] = output
            records[path] = {"sha256": hashlib.sha256(raw).hexdigest(), "observed_defaults": selected}
        results[name] = {"commit": head, "sources": records, "errors": evidence_output_errors(defaults)}
    assert not results["fishhat"]["errors"]
    assert len(results["riverhog"]["errors"]) == 4
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
