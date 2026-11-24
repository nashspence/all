import json
from pathlib import Path
import subprocess


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def verify_publication(root, repository, publication, proffer_errors):
    errors = proffer_errors(publication)
    if errors:
        raise ValueError(errors)
    if publication["kind"] != "publication" or publication["supplied"]["kind"] != "commit":
        raise ValueError("this adapter verifies Git publications only")
    published = publication["handoff"]["commit"]
    supplied = publication["supplied"]["id"]
    for commit in (published, supplied):
        if _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}") != commit:
            raise ValueError("commit identity is not exact")
    expected_url = f"https://github.com/{repository}/blob/{published}/.reference/proffer.json"
    if publication["handoff"]["url"] != expected_url:
        raise ValueError("publication URL differs from verified artifact")
    method = publication["verification"]["method"]
    if method == "commit-identity":
        if supplied != published:
            raise ValueError("different commits")
    elif method == "tree-identity":
        if _git(root, "rev-parse", f"{supplied}^{{tree}}") != _git(root, "rev-parse", f"{published}^{{tree}}"):
            raise ValueError("different trees")
    else:
        raise ValueError("archive inventories need their own adapter")
    handoff = json.loads(_git(root, "show", f"{published}:.reference/proffer.json"))
    errors = proffer_errors(handoff)
    if errors or handoff["kind"] != "handoff" or handoff["issue"] != publication["issue"]:
        raise ValueError("published handoff does not match owning issue or schema")
    return handoff
