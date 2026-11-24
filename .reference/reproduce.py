import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True


HEADS = {
    "guavajam": "54fce07b619628a5e92be946be4b189873ddf1a0",
    "forgejo-restic-restore-bootstrap": "5e64256f72a0baccfe85eed81d126d77b2fe59ab",
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare(repositories):
    for name, expected in HEADS.items():
        head = subprocess.check_output(["git", "-C", str(repositories / name), "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(repositories / name), "status", "--porcelain"], text=True)
        if head != expected or status:
            raise ValueError(f"{name}: inspect the recorded source commit")
    restore = load("restore_fixture", repositories / "forgejo-restic-restore-bootstrap/tests/test_profiles.py")
    guavajam = load("guavajam_fixture", repositories / "guavajam/tests/support/guavajam_test_support/discovery_fixture.py")
    results = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config = root / "ambient.gitconfig"
        config.write_text("[commit]\n gpgsign = true\n[gpg]\n program = /nonexistent/fixture-signer\n")
        for mode in ("baseline", "global-signing", "injected-signing"):
            environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
            environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
            if mode == "global-signing":
                environment["GIT_CONFIG_GLOBAL"] = str(config)
            elif mode == "injected-signing":
                environment.update(GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="true",
                                   GIT_CONFIG_KEY_1="gpg.program", GIT_CONFIG_VALUE_1="/nonexistent/fixture-signer")
            with patch.dict(os.environ, environment, clear=True):
                for name, create in (
                    ("forgejo-restic-restore-bootstrap", lambda path: restore.make_bare_repo(path, "/repo.git")),
                    ("guavajam", guavajam.Draft),
                ):
                    owned = root / f"{mode}-{name}"
                    owned.mkdir()
                    try:
                        create(owned)
                        passed = True
                    except subprocess.CalledProcessError as error:
                        if error.returncode != 128 or "fixture-signer" not in (error.stderr or ""):
                            raise
                        passed = False
                    results.append({"mode": mode, "repository": name, "passed": passed})
    expected = [True, True, False, True, False, False]
    if [row["passed"] for row in results] != expected:
        raise AssertionError(results)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exercise actual recorded owner fixtures using only disposable local state.")
    parser.add_argument("--repos", dest="repositories", type=Path, required=True, help="directory containing the two exact recorded Git checkouts")
    print(json.dumps(compare(parser.parse_args().repositories.resolve()), indent=2))
