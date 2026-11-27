"""Append compact first-attempt decision receipts to dedicated Git history.

Only the trusted main workflow receives a write token. Reports are data; the
publisher never imports or executes anything from a downloaded artifact.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = "nashspence/all"
PREFIX = "/repos/" + REPOSITORY
BRANCH = "profile-evidence"
MAX_FILE_BYTES = 4 * 1024**2
MAX_REPORT_BYTES = 64 * 1024**2
MAX_RESPONSE_BYTES = 8 * 1024**2
OUTCOMES = {"pass", "environment", "failed", "incomplete"}


class PublicationError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise PublicationError("GitHub redirect refused")


class GitHub:
    def __init__(self, token):
        if not token:
            raise PublicationError("GITHUB_TOKEN is required for evidence publication")
        self.headers = {"Authorization": "Bearer " + token,
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "User-Agent": "nashspence-all-profile-refresh"}
        self.opener = build_opener(_NoRedirect())

    def request(self, method, path, data=None, **query):
        if not path.startswith(PREFIX + "/") or "?" in path or "#" in path:
            raise PublicationError("unsupported publication endpoint")
        url = "https://api.github.com" + path
        if query:
            url += "?" + urlencode(query)
        request = Request(url, headers=self.headers, method=method,
                          data=None if data is None else _encode(data))
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise PublicationError("GitHub response exceeds publication bound")
            return _decode(raw)
        except HTTPError:
            # Callers distinguish missing refs and non-fast-forward races.
            raise
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise PublicationError("GitHub publication request failed: " + type(error).__name__) from None

    def get(self, path, **query):
        return self.request("GET", path, **query)

    def first_attempt_jobs(self, run_id):
        rows, total = [], None
        for page in range(1, 21):
            result = self.get(f"{PREFIX}/actions/runs/{run_id}/attempts/1/jobs",
                              per_page=100, page=page)
            batch = result.get("jobs")
            count = result.get("total_count")
            if not isinstance(batch, list) or type(count) is not int or count < 0:
                raise PublicationError("invalid first-attempt job inventory")
            if total is not None and count != total:
                raise PublicationError("first-attempt job inventory changed while reading")
            total = count
            rows.extend(batch)
            if len(batch) < 100:
                if len(rows) != total or len({row.get("id") for row in rows}) != len(rows):
                    raise PublicationError("incomplete or duplicate first-attempt job inventory")
                return rows
        raise PublicationError("first-attempt job inventory exceeds publication bound")


def _encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("non-finite JSON number")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _positive(value):
    return type(value) is int and value > 0


def read_reports(directory):
    """Retain exact UTF-8 bytes and parsing failures, within a fixed input bound."""
    root = Path(directory).resolve()
    retained, packets, errors, total = {}, {}, [], 0
    for path in sorted(root.rglob("worker-*.json")):
        relative = str(path.relative_to(root))
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            errors.append(relative + ": not a regular owned report")
            continue
        size = path.stat().st_size
        total += size
        if size > MAX_FILE_BYTES or total > MAX_REPORT_BYTES:
            raise PublicationError("worker reports exceed publication size bound")
        raw = path.read_bytes()
        retained[relative] = {"sha256": _sha(raw), "bytes": len(raw),
                              "base64": base64.b64encode(raw).decode("ascii")}
        match = re.fullmatch(r"worker-([12])-(1[0-2]|[1-9])\.json", path.name)
        if not match:
            errors.append(relative + ": unexpected report filename")
            continue
        key = tuple(map(int, match.groups()))
        if key in packets:
            packets[key] = None
            errors.append(relative + ": duplicate worker report")
            continue
        try:
            packet = _decode(raw)
            if not isinstance(packet, dict):
                raise ValueError("worker report is not an object")
            packets[key] = packet
        except (ValueError, UnicodeError):
            packets[key] = None
            errors.append(relative + ": invalid worker report JSON")
    return retained, packets, errors


def collect(client, *, reports, kind, source, source_digest, workflow,
            workflow_digest, bootstrap=False, environment=None, now=None,
            classifier=None, artifact_verifier=None):
    """Bind each declared slot to GitHub's original allocation, never its claim."""
    env = os.environ if environment is None else environment
    now = now or _utc_now()
    expected_workflow = f".github/workflows/{kind}-profile-refresh.yml"
    if (kind not in {"core", "storage"} or workflow != expected_workflow
            or not re.fullmatch(r"[0-9a-f]{40}", source)
            or not re.fullmatch(r"[0-9a-f]{64}", source_digest)
            or not re.fullmatch(r"[0-9a-f]{64}", workflow_digest)
            or (bootstrap and kind != "core")):
        raise PublicationError("invalid frozen publication identity")
    if (env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REPOSITORY") != REPOSITORY
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or env.get("GITHUB_EVENT_NAME") not in {"push", "schedule", "workflow_dispatch"}):
        raise PublicationError("publication requires a real first-attempt main workflow")
    try:
        run_id = int(env["GITHUB_RUN_ID"])
    except (KeyError, ValueError):
        raise PublicationError("invalid run identity") from None
    if run_id <= 0:
        raise PublicationError("invalid run identity")
    run = client.get(f"{PREFIX}/actions/runs/{run_id}")
    workflow_sha = env.get("GITHUB_WORKFLOW_SHA") or env.get("REFRESH_WORKFLOW_SHA")
    if (run.get("id") != run_id or run.get("run_attempt") != 1
            or run.get("head_branch") != "main" or run.get("path") != workflow
            or run.get("head_sha") != env.get("GITHUB_SHA")
            or run.get("head_sha") != workflow_sha
            or run.get("event") != env.get("GITHUB_EVENT_NAME")
            or run.get("repository", {}).get("full_name") != REPOSITORY
            or run.get("head_repository", {}).get("full_name") != REPOSITORY):
        raise PublicationError("GitHub run does not match trusted main publication context")
    contents = client.get(f"{PREFIX}/contents/{workflow}", ref=workflow_sha)
    try:
        workflow_bytes = base64.b64decode("".join(contents["content"].split()), validate=True)
    except (KeyError, ValueError, TypeError):
        raise PublicationError("cannot verify actual workflow bytes") from None
    if contents.get("encoding") != "base64" or _sha(workflow_bytes) != workflow_digest:
        raise PublicationError("actual workflow differs from claimed workflow identity")
    jobs = client.first_attempt_jobs(run_id)
    retained, packets, errors = read_reports(reports)
    if artifact_verifier is None:
        from .refresh_artifacts import verify
        artifact_verifier = verify
    artifacts, artifact_errors = artifact_verifier(client, run_id, kind, retained,
                                                   cohorts=2 if bootstrap else 1)
    if classifier is None:
        from .refresh_collect import classify
        classifier = classify
    cohorts, all_runners = [], set()
    previous_end = run.get("run_started_at") or run["created_at"]
    for cohort in range(1, 3 if bootstrap else 2):
        workers, completed = [], []
        for slot in range(1, 13):
            name = f"core-{cohort}-{slot}" if kind == "core" else f"storage-{slot}"
            matches = [job for job in jobs if job.get("name") == name]
            job = matches[0] if len(matches) == 1 else {}
            runner_id = job.get("runner_id") if _positive(job.get("runner_id")) else 0
            packet = packets.get((cohort, slot))
            outcome = "incomplete"
            reason = None
            if not job or job.get("status") != "completed" or not runner_id:
                reason = "missing or incomplete original allocation"
            elif runner_id in all_runners:
                reason = "runner allocation reused within campaign"
            elif (cohort, slot) in artifact_errors:
                reason = "artifact integrity: " + artifact_errors[cohort, slot]
            elif not isinstance(packet, dict):
                reason = "missing, duplicate or malformed report"
            elif any(type(packet.get(key)) is not type(expected) or packet.get(key) != expected for key, expected in {
                    "schema": 1, "run_id": run_id, "run_attempt": 1,
                    "cohort": cohort, "slot": slot, "source_commit": source,
                    "source_digest": source_digest, "workflow_sha": workflow_sha,
                    "runner_name": job.get("runner_name")}.items()):
                reason = "report provenance differs from original allocation"
            elif not any(step.get("name") == "Upload retained evidence"
                         and step.get("conclusion") == "success"
                         for step in job.get("steps", [])):
                reason = "original allocation did not retain its artifact successfully"
            else:
                try:
                    outcome = classifier(packet, kind, source_digest)
                    if outcome not in OUTCOMES:
                        raise ValueError("unknown classification")
                    if outcome in {"pass", "environment"} and job.get("conclusion") != "success":
                        outcome, reason = "incomplete", "non-successful original worker job"
                    if kind == "storage" and outcome == "environment":
                        outcome, reason = "failed", "storage has no environmental allowance"
                except Exception as error:
                    outcome, reason = "incomplete", "classification failed: " + type(error).__name__
            if runner_id:
                all_runners.add(runner_id)
            if reason:
                errors.append(name + ": " + reason)
            if isinstance(job.get("completed_at"), str):
                completed.append(job["completed_at"])
            workers.append({"slot": slot, "runner_id": runner_id, "outcome": outcome})
        previous_end = max([previous_end] + (completed or [now]))
        cohorts.append({"workers": workers, "completed_at": previous_end})
    expected_keys = {(cohort, slot) for cohort in range(1, len(cohorts) + 1) for slot in range(1, 13)}
    if packets.keys() - expected_keys or errors:
        # A rogue/duplicate report cannot hide behind twelve otherwise-good rows.
        # Existing per-worker failures retain their precise classification.
        if all(worker["outcome"] in {"pass", "environment"}
               for cohort in cohorts for worker in cohort["workers"]):
            cohorts[0]["workers"][0]["outcome"] = "incomplete"
        if packets.keys() - expected_keys:
            errors.append("reports include undeclared campaign slots")
    # Keep the original worker bytes in their expiring Actions artifacts.
    # The diagnostic verification report need not duplicate their payloads.
    evidence = {"schema": 1, "run": run, "jobs": jobs,
                "reports": {name: {key: value for key, value in record.items() if key != "base64"}
                            for name, record in retained.items()},
                "artifacts": artifacts, "errors": errors, "published_at": now}
    raw = _encode(evidence)
    summary = {"run_id": run_id, "workflow": workflow, "source_commit": source,
               "source_digest": source_digest, "workflow_digest": workflow_digest,
               "run_attempt": 1, "event": run["event"], "ref": "refs/heads/main",
               "created_at": run["created_at"], "started_at": run.get("run_started_at"),
               "completed_at": max([now] + [row["completed_at"] for row in cohorts]),
               "cohorts": cohorts, "evidence_path": f"runs/{run_id}.json",
               "evidence_sha256": _sha(raw)}
    return summary, raw


def _receipt_exists(client, head, path):
    if head is None:
        return False
    try:
        client.get(f"{PREFIX}/contents/{path}", ref=head)
        return True
    except HTTPError as error:
        if error.code != 404:
            raise
        return False


def append(client, summary, evidence, *, attempts=3):
    """Append decision records using non-forced ancestry; never store packets."""
    if _sha(evidence) != summary["evidence_sha256"]:
        raise PublicationError("evidence digest differs from summary")
    from .approval import REGISTRY_PATH, _content
    from .refresh import (INDEX_WARNING_BYTES, MAX_INDEX_BYTES, compact_index,
                          validate_index, validate_registry)
    registry = validate_registry(_decode(_content(client, REGISTRY_PATH, summary["source_commit"])))
    when = datetime.fromisoformat(summary["completed_at"].replace("Z", "+00:00"))
    for attempt in range(attempts):
        head, tree = None, None
        try:
            head = client.get(f"{PREFIX}/git/ref/heads/{BRANCH}")["object"]["sha"]
        except HTTPError as error:
            if error.code != 404:
                raise
        if head:
            commit = client.get(f"{PREFIX}/git/commits/{head}")
            tree = commit["tree"]["sha"]
            contents = client.get(f"{PREFIX}/contents/index.json", ref=head)
            if contents.get("encoding") != "base64":
                raise PublicationError("evidence index is not a regular JSON file")
            raw_index = base64.b64decode("".join(contents["content"].split()), validate=True)
            if len(raw_index) > MAX_INDEX_BYTES:
                raise PublicationError("existing index exceeds publication capacity; reviewed maintenance required")
            index = _decode(raw_index)
        else:
            index = {"schema": 1, "runs": []}
        validate_index(index)
        if (any(row["run_id"] == summary["run_id"] for row in index["runs"])
                or _receipt_exists(client, head, summary["evidence_path"])):
            raise PublicationError("run already recorded; first-attempt evidence cannot be replaced")
        missing = missing_publications(client, summary, {row["run_id"] for row in index["runs"]})
        # Reuse an immutable receipt if a previously compacted original is
        # encountered in the live inventory. Never recreate it as a tombstone.
        recovered, new_missing = [], []
        for row, raw in missing:
            path = row["evidence_path"]
            try:
                prior = _decode(_content(client, path, head)) if head else None
            except HTTPError as error:
                if error.code != 404:
                    raise
                prior = None
            if prior is None:
                new_missing.append((row, raw))
            else:
                validate_index({"schema": 1, "runs": [prior]})
                if (prior["run_id"] != row["run_id"] or prior["workflow"] != row["workflow"]
                        or prior["created_at"] != row["created_at"] or prior["event"] != row["event"]):
                    raise PublicationError("historical receipt identity mismatch")
                recovered.append(prior)
        index["runs"].extend(recovered)
        index["runs"].extend(row for row, _ in new_missing)
        index["runs"].append(summary)
        index["runs"].sort(key=lambda row: (row["created_at"], row["run_id"]))
        index = compact_index(registry, index, when)
        encoded_index = _encode(index)
        if len(encoded_index) > MAX_INDEX_BYTES:
            raise PublicationError("index capacity exhausted; reviewed epoch renewal required")
        if len(encoded_index) >= INDEX_WARNING_BYTES:
            print("::warning::Profile evidence index approaching capacity; review enrollment before exhaustion")
        elements = []
        # The receipt's evidence_sha256 commits to its expiring verification
        # report. The compact receipt itself supplies replay detection.
        files = [(row["evidence_path"], _encode(row)) for row, _ in new_missing]
        files.extend(((summary["evidence_path"], _encode(summary)), ("index.json", encoded_index)))
        for path, raw in files:
            blob = client.request("POST", f"{PREFIX}/git/blobs",
                                  {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"})
            elements.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tree_args = {"tree": elements}
        if tree:
            tree_args["base_tree"] = tree
        created_tree = client.request("POST", f"{PREFIX}/git/trees", tree_args)
        created_commit = client.request("POST", f"{PREFIX}/git/commits", {
            "message": f"Record original profile refresh {summary['run_id']}",
            "tree": created_tree["sha"], "parents": [head] if head else []})
        try:
            if head:
                client.request("PATCH", f"{PREFIX}/git/refs/heads/{BRANCH}",
                               {"sha": created_commit["sha"], "force": False})
            else:
                client.request("POST", f"{PREFIX}/git/refs",
                               {"ref": "refs/heads/" + BRANCH, "sha": created_commit["sha"]})
            return created_commit["sha"]
        except HTTPError as error:
            if error.code not in {409, 422} or attempt + 1 == attempts:
                raise
            new_head = client.get(f"{PREFIX}/git/ref/heads/{BRANCH}")["object"]["sha"]
            if new_head == head:
                raise PublicationError("evidence append rejected without a concurrent publication") from None
    raise PublicationError("evidence append exhausted concurrent update bound")


def missing_publications(client, summary, recorded):
    """A later green publication records, rather than forgets, a lost publisher."""
    when = datetime.fromisoformat(summary["completed_at"].replace("Z", "+00:00"))
    since = (when - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    workflow = summary["workflow"]
    path = f"{PREFIX}/actions/workflows/{workflow.rsplit('/', 1)[-1]}/runs"
    runs, total = [], None
    for page in range(1, 21):
        response = client.get(path, branch="main", created=">=" + since, per_page=100, page=page)
        batch, count = response.get("workflow_runs"), response.get("total_count")
        if (not isinstance(batch, list) or type(count) is not int or not 0 <= count < 1000
                or (total is not None and count != total)):
            raise PublicationError("incomplete canonical refresh inventory")
        total = count
        runs.extend(batch)
        if len(batch) < 100:
            if len(runs) != total or len({run.get("id") for run in runs}) != total:
                raise PublicationError("incomplete or duplicated canonical refresh inventory")
            break
    else:
        raise PublicationError("canonical refresh inventory exceeds publication bound")
    missing = []
    for run in runs:
        identity = run.get("id")
        if (not _positive(identity) or not isinstance(run.get("created_at"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", run.get("head_sha", ""))):
            raise PublicationError("invalid canonical refresh run")
        if (identity in recorded or identity == summary["run_id"]
                or run["created_at"] >= summary["created_at"] or run.get("status") != "completed"
                or run.get("path") != workflow or run.get("head_branch") != "main"
                or run.get("event") not in {"push", "schedule", "workflow_dispatch"}):
            continue
        original = client.get(f"{PREFIX}/actions/runs/{identity}/attempts/1")
        if (original.get("id") != identity or original.get("run_attempt") != 1
                or original.get("path") != workflow or original.get("head_branch") != "main"
                or original.get("event") != run["event"]):
            raise PublicationError("original missing-publication identity is inconsistent")
        jobs = client.first_attempt_jobs(identity)
        count = 2 if any(re.fullmatch(r"core-2-(?:[1-9]|1[0-2])", job.get("name", ""))
                         for job in jobs) else 1
        started = original.get("run_started_at")
        completed = max([original.get("updated_at") or summary["completed_at"],
                         started or original["created_at"]] +
                        [job["completed_at"] for job in jobs if isinstance(job.get("completed_at"), str)])
        raw = _encode({"schema": 1, "run": original, "jobs": jobs, "reports": {},
                       "errors": ["original refresh completed without durable publication"],
                       "published_at": summary["completed_at"]})
        tombstone = {"run_id": identity, "workflow": workflow,
                     "source_commit": original["head_sha"], "source_digest": "0" * 64,
                     "workflow_digest": "0" * 64, "run_attempt": 1, "event": original["event"],
                     "ref": "refs/heads/main", "created_at": original["created_at"],
                     "started_at": started, "completed_at": completed,
                     "cohorts": [{"completed_at": completed, "workers": [
                         {"slot": slot, "runner_id": 0, "outcome": "incomplete"}
                         for slot in range(1, 13)]} for _ in range(count)],
                     "evidence_path": f"runs/{identity}.json", "evidence_sha256": _sha(raw)}
        missing.append((tombstone, raw))
    return missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--kind", choices=("core", "storage"), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-digest", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--workflow-digest", required=True)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--verification-report", type=Path, required=True,
                        help="owned output for expiring Actions diagnostic artifact")
    args = parser.parse_args(argv)
    report = args.verification_report
    del args.verification_report
    try:
        client = GitHub(os.environ.get("GITHUB_TOKEN"))
        summary, evidence = collect(client, **vars(args))
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_bytes(evidence)
        revision = append(client, summary, evidence)
        print(json.dumps({"evidence_commit": revision, "run": summary}, sort_keys=True))
        workers = [worker for cohort in summary["cohorts"] for worker in cohort["workers"]]
        acceptable = all(worker["outcome"] in {"pass", "environment"} for worker in workers)
        if args.kind == "core" and sum(worker["outcome"] == "environment" for worker in workers) > 1:
            acceptable = False
        return 0 if acceptable else 1
    except (PublicationError, HTTPError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": "refresh publication failed: " + str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
