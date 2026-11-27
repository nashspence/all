"""Current shared approval, read from fixed GitHub authorities before acceptance."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

PREFIX = "/repos/nashspence/all"
REGISTRY_PATH = ".all/performance/approvals.json"
EVIDENCE_BRANCH = "profile-evidence"
MAX_BYTES = 2 * 1024 * 1024
MAX_PAGES = 20
EVENTS = {"push", "schedule", "workflow_dispatch"}


class ApprovalError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise ApprovalError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate key in shared approval JSON")
        result[key] = value
    return result


def _json(data):
    def invalid_constant(unused):
        raise ApprovalError("nonfinite number in shared approval JSON")
    try:
        return json.loads(data, object_pairs_hook=_pairs, parse_constant=invalid_constant)
    except (ValueError, UnicodeError):
        raise ApprovalError("invalid shared approval JSON") from None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class _GitHub:
    def __init__(self):
        self.opener = build_opener(_NoRedirect())
        self.headers = {"Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "User-Agent": "nashspence-all-profile-approval"}
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get(self, path, **query):
        _require(path.startswith(PREFIX + "/") and "?" not in path
                 and "#" not in path and ".." not in path,
                 "approval requests must use the fixed repository")
        url = "https://api.github.com" + path
        if query:
            url += "?" + urlencode(query)
        try:
            with self.opener.open(Request(url, headers=self.headers), timeout=10) as response:
                _require(response.geturl() == url, "approval redirects are forbidden")
                data = response.read(MAX_BYTES + 1)
        except HTTPError as error:
            raise ApprovalError(f"shared approval HTTP {error.code}; no cached acceptance") from None
        except (URLError, TimeoutError, OSError):
            raise ApprovalError("shared approval unavailable; no cached acceptance") from None
        _require(len(data) <= MAX_BYTES, "shared approval response exceeds 2 MiB")
        return _json(data)


def _source_files(package_root=None):
    package = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    files = {}
    for path in sorted(package.rglob("*.py")):
        _require(path.is_file() and not path.is_symlink(), "package source must be regular files")
        files["all_policy/" + path.relative_to(package).as_posix()] = path.read_bytes()
    _require("all_policy/__init__.py" in files, "installed package source is unavailable")
    return files


def _digest(files):
    hashes = {path: hashlib.sha256(data).hexdigest() for path, data in files.items()}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_digest(package_root=None):
    """Hash all installed package Python sources; tests and bytecode are excluded."""
    return _digest(_source_files(package_root))


def _head(client, branch):
    data = client.get(f"{PREFIX}/git/ref/heads/{quote(branch, safe='')}")
    value = data.get("object", {}) if isinstance(data, dict) else {}
    _require(value.get("type") == "commit" and isinstance(value.get("sha"), str)
             and re.fullmatch(r"[0-9a-f]{40}", value["sha"]), "invalid shared authority ref")
    return value["sha"]


def _content(client, path, revision):
    document = client.get(f"{PREFIX}/contents/{quote(path, safe='/')}", ref=revision)
    _require(isinstance(document, dict) and document.get("type") == "file"
             and document.get("encoding") == "base64" and isinstance(document.get("content"), str),
             "shared authority must be a regular file")
    try:
        data = base64.b64decode("".join(document["content"].split()), validate=True)
    except ValueError:
        raise ApprovalError("invalid shared authority encoding") from None
    _require(len(data) <= MAX_BYTES, "shared authority exceeds 2 MiB")
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    _require(document.get("sha") == blob, "shared authority blob identity mismatch")
    return data


def _current_source(client, main, files):
    tree = client.get(f"{PREFIX}/git/trees/{main}", recursive=1)
    _require(isinstance(tree, dict) and tree.get("truncated") is False
             and isinstance(tree.get("tree"), list), "incomplete current shared source tree")
    actual = {}
    for entry in tree["tree"]:
        _require(isinstance(entry, dict) and isinstance(entry.get("path"), str),
                 "invalid current shared source tree")
        path = entry["path"]
        if path.startswith("all_policy/") and path.endswith(".py"):
            _require(path not in actual and entry.get("type") == "blob"
                     and entry.get("mode") in {"100644", "100755"},
                     "invalid current shared source entry")
            actual[path] = entry.get("sha")
    expected = {path: hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                for path, data in files.items()}
    _require(actual == expected, "current all/main implementation differs from the installed package")


def _utc(value):
    _require(isinstance(value, str) and value.endswith("Z"), "missing workflow creation timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ApprovalError("invalid workflow creation timestamp") from None


def _workflow_runs(client, entry, index, now):
    from .refresh import LIVE_WINDOW

    workflow = entry["workflow"]
    anchored = {run["run_id"]: run for run in index["runs"]
                if run["run_id"] in entry["qualification_runs"]}
    _require(set(anchored) == set(entry["qualification_runs"]),
             "shared approval qualification evidence is missing")
    earliest = max(min(_utc(run["created_at"]) for run in anchored.values()), now - LIVE_WINDOW)
    cutoff = earliest.isoformat().replace("+00:00", "Z")
    runs, seen = [], set()
    path = f"{PREFIX}/actions/workflows/{quote(workflow.rsplit('/', 1)[-1], safe='')}/runs"
    for page in range(1, MAX_PAGES + 1):
        result = client.get(path, branch="main", created=">=" + cutoff,
                            per_page=100, page=page)
        _require(isinstance(result, dict) and type(result.get("total_count")) is int
                 and 0 <= result["total_count"] < 1000
                 and isinstance(result.get("workflow_runs"), list),
                 "workflow history incomplete or exceeds GitHub's 1,000-result search limit")
        batch = result["workflow_runs"]
        _require(len(batch) <= 100, "invalid workflow history page")
        for run in batch:
            _require(isinstance(run, dict) and type(run.get("id")) is int
                     and run["id"] > 0 and run["id"] not in seen,
                     "workflow history changed during pagination; retry acceptance")
            seen.add(run["id"])
            _require(_utc(run.get("created_at")) >= earliest,
                     "workflow history does not cover the requested epoch")
            if (run.get("path") == workflow and run.get("head_branch") == "main"
                    and run.get("event") in EVENTS):
                if type(run.get("run_attempt")) is int and run["run_attempt"] > 1:
                    original = client.get(f"{PREFIX}/actions/runs/{run['id']}/attempts/1")
                    _require(isinstance(original, dict) and original.get("run_attempt") == 1
                             and all(original.get(key) == run.get(key) for key in
                                     ("id", "path", "head_branch", "head_sha", "event", "created_at")),
                             "original workflow attempt identity mismatch")
                    run = original
                runs.append(run)
        if len(batch) < 100:
            _require(len(seen) == result["total_count"], "incomplete workflow history")
            return runs
    raise ApprovalError("workflow history exceeds bounded pagination")


def _require_current(profiles, client, now):
    from .refresh import evaluate, validate_index, validate_registry

    main = _head(client, "main")
    registry = validate_registry(_json(_content(client, REGISTRY_PATH, main)))
    _require(profiles <= set(registry["profiles"]), "requested profile has no current shared approval")
    files = _source_files()
    digest = _digest(files)
    _current_source(client, main, files)
    evidence = _head(client, EVIDENCE_BRANCH)
    index = validate_index(_json(_content(client, "index.json", evidence)))
    results, workflows = {}, {}
    for profile in sorted(profiles):
        entry = registry["profiles"][profile]
        _require(entry["source_digest"] == digest, "installed package is not the approved implementation")
        workflow = entry["workflow"]
        if workflow not in workflows:
            workflow_digest = hashlib.sha256(_content(client, workflow, main)).hexdigest()
            workflows[workflow] = workflow_digest
        _require(workflows[workflow] == entry["workflow_digest"],
                 "current refresh workflow differs from its reviewed approval")
        observed = _workflow_runs(client, entry, index, now)
        result = evaluate(registry, index, profile, digest, now, observed_runs=observed)
        _require(result["status"] == "active",
                 f"shared profile {profile} is {result['status']}: " + "; ".join(result["reasons"]))
        results[profile] = dict(result, registry_commit=main, evidence_commit=evidence,
                                checked_at=now.isoformat().replace("+00:00", "Z"))
    return results


def require_current(profiles):
    """Require current shared approval; no local manifest or cached green is accepted."""
    _require(isinstance(profiles, set) and all(isinstance(profile, str) for profile in profiles),
             "profiles must be a set of profile identifiers")
    if not profiles:
        return {}
    try:
        return _require_current(profiles, _GitHub(), datetime.now(timezone.utc))
    except ApprovalError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        raise ApprovalError("invalid or unavailable shared approval") from None


def main(argv=None):
    from .profiles import CORE, PREPARED_EXT4

    parser = argparse.ArgumentParser(prog="all-policy performance-status")
    parser.add_argument("profiles", metavar="PROFILE", nargs="*",
                        help="profile IDs; defaults to core and prepared storage")
    arguments = parser.parse_args(argv)
    try:
        result = require_current(set(arguments.profiles or [CORE, PREPARED_EXT4]))
    except ApprovalError as error:
        print(json.dumps({"status": "unavailable", "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
