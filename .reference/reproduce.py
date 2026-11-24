import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from policy import typing_errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=Path, required=True)
    args = parser.parse_args()
    selected = (
        ("all", "03de186a044c9c6b365347485a6c4093ce831c79", ".", "all_policy"),
        ("fishhat", "f96b83dc20f059d62a4363a63c37bb0ef8c642e5", "packages/fishhat-contracts", "fishhat_contracts"),
    )
    results = {}
    for name, expected, project, module in selected:
        repo = args.repos.resolve() / name
        head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True)
        if head != expected or status:
            raise ValueError(f"{name}: expected clean audited commit {expected}")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            shutil.copytree(repo / project, source, symlinks=True,
                            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.egg-info", "build", "dist"))
            out = root / "wheels"
            script = "import setuptools.build_meta; print(setuptools.build_meta.build_wheel(" + repr(str(out)) + "))"
            build = subprocess.run([sys.executable, "-c", script], cwd=source, text=True, capture_output=True)
            if build.returncode:
                raise RuntimeError(build.stdout + build.stderr)
            wheel = out / build.stdout.strip().splitlines()[-1]
            with zipfile.ZipFile(wheel) as archive:
                markers = [item for item in archive.namelist() if item.endswith("/py.typed")]
            results[name] = {"commit": head, "wheel": wheel.name, "markers": markers,
                             "policy_errors": typing_errors(wheel, [module])}
    assert results["all"]["policy_errors"] and not results["fishhat"]["policy_errors"]
    print(json.dumps({"build_backend_version": importlib.metadata.version("setuptools"), "results": results}, indent=2))


if __name__ == "__main__":
    main()
