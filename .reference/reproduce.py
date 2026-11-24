import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


parser = argparse.ArgumentParser()
parser.add_argument("--repos", type=Path, required=True)
root = parser.parse_args().repos.resolve()
heads = {"riverhog": "be483fd6d567616d5fcd355202d61f1e682efe75",
         "fishhat": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5"}
for name, commit in heads.items():
    assert subprocess.check_output(["git", "-C", str(root / name), "rev-parse", "HEAD"], text=True).strip() == commit
    subprocess.run(["git", "-C", str(root / name), "diff", "--quiet", "HEAD", "--"], check=True)
sys.path[:0] = [str(root / "riverhog/packages/config-validation/src"), str(root / "fishhat/packages/fishhat-contracts/src")]
from config_validation import load_yaml_config
from fishhat_contracts.validation import strict_yaml
source = "enabled: yes\nlabel: on\ncount: 010\nseconds: 1:20\n"
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / "config.yaml"
    path.write_text(source)
    riverhog = load_yaml_config(path)
fishhat = strict_yaml(source)
assert riverhog == {"enabled": True, "label": True, "count": 8, "seconds": 80}
assert fishhat == {"enabled": "yes", "label": "on", "count": "010", "seconds": "1:20"}
print(json.dumps({"riverhog": riverhog, "fishhat": fishhat}, sort_keys=True))
