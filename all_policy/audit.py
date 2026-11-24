import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .protocol import POLICY_PATH, SOURCE_REPOSITORY, WORKFLOW_PATH, check_workflow


@dataclass(frozen=True)
class Result:
    repository: str
    errors: tuple[str, ...] = ()


class AuditError(RuntimeError):
    pass


class GitHub:
    def __init__(self, token=None):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "nashspence-all",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get(self, path, **query):
        url = f"https://api.github.com{path}"
        if query:
            url += "?" + urlencode(query)
        try:
            with urlopen(Request(url, headers=self.headers), timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            raise AuditError(f"GitHub HTTP {error.code}: {path}") from None
        except (URLError, TimeoutError, OSError):
            raise AuditError(f"GitHub unavailable: {path}") from None
        except (ValueError, UnicodeError):
            raise AuditError(f"GitHub returned invalid JSON: {path}") from None

    def pages(self, path, *, key=None, **query):
        page = 1
        while True:
            response = self.get(path, per_page=100, page=page, **query)
            batch = (response.get(key) if isinstance(response, dict) else None) if key else response
            if not isinstance(batch, list):
                raise AuditError(f"GitHub returned an invalid page: {path}")
            yield from batch
            if len(batch) < 100:
                return
            page += 1


def _inventory(client, owner, authenticated):
    errors = []
    user = None
    if authenticated:
        try:
            user = client.get("/user")
            if user.get("login", "").lower() != owner.lower():
                raise AuditError("ALL_REPOS_TOKEN must belong to the audited owner")
        except (AuditError, AttributeError, KeyError, TypeError, ValueError) as error:
            errors.append(str(error))
            user = None
    else:
        errors.append("ALL_REPOS_TOKEN is required to verify private-repository inventory; auditing public repositories only")
    if user is None:
        repositories = list(client.pages(f"/users/{quote(owner, safe='')}/repos", type="owner"))
    else:
        repositories = list(client.pages("/user/repos", affiliation="owner", visibility="all"))
    owned = {
        repo["full_name"]: repo
        for repo in repositories
        if repo["owner"]["login"].lower() == owner.lower()
    }
    if not owned:
        errors.append("no owned repositories returned")
    if user is not None:
        for field, private in (("public_repos", False), ("owned_private_repos", True)):
            expected = user.get(field)
            actual = sum(repo.get("private") is private for repo in owned.values())
            if type(expected) is not int or expected != actual:
                errors.append(f"incomplete inventory: {field}={expected!r}, visible={actual}")
    return sorted(owned.values(), key=lambda repo: repo["full_name"]), tuple(errors)


def _head(client, repository, branch):
    return client.get(f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}")["object"]["sha"]


def _run_order(run):
    timestamp = run.get("run_started_at")
    if timestamp is None and run.get("status") in {"queued", "requested", "waiting", "pending"}:
        timestamp = run.get("created_at")
    try:
        started = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if started.tzinfo is None:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise AuditError("cannot order policy runs: missing or invalid execution timestamp") from None
    return started, run["id"]


def _check_repository(client, repo, policy_sha, now):
    repository = repo["full_name"]
    branch = repo["default_branch"]
    head = _head(client, repository, branch)
    prefix = f"/repos/{repository}"
    contents = client.get(f"{prefix}/contents/{WORKFLOW_PATH}", ref=head)
    if contents.get("encoding") != "base64":
        raise AuditError(f"{WORKFLOW_PATH} must be a regular UTF-8 file")
    text = base64.b64decode("".join(contents["content"].split()), validate=True).decode("utf-8")
    errors = list(check_workflow(text, repository))
    if errors:
        return tuple(errors)
    workflow_path = f"{prefix}/actions/workflows/{WORKFLOW_PATH.rsplit('/', 1)[-1]}"
    workflow = client.get(workflow_path)
    if workflow.get("state") != "active" or workflow.get("path") != WORKFLOW_PATH:
        errors.append("policy workflow is not active")
    runs = [
        run for run in client.pages(
            workflow_path + "/runs", key="workflow_runs", branch=branch,
            head_sha=head, exclude_pull_requests="true",
        )
        if run.get("head_sha") == head and run.get("head_branch") == branch
        and run.get("event") in {"push", "schedule", "workflow_dispatch"}
    ]
    if not runs:
        return tuple(errors + ["no policy run for the current default-branch commit"])
    run_path = f"{prefix}/actions/runs/{max(runs, key=_run_order)['id']}"
    run = client.get(run_path)
    if (run.get("head_sha"), run.get("head_branch")) != (head, branch):
        errors.append("policy run does not cover the current default-branch commit")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        errors.append("latest policy run is not successful")
    timestamp = run.get("run_started_at")
    started = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if isinstance(timestamp, str) else None
    if started is None or started.tzinfo is None or not timedelta(minutes=-5) <= now - started <= timedelta(hours=48):
        errors.append("latest policy run is not fresh (48 hours)")
    allowed_paths = {f"{SOURCE_REPOSITORY}/{POLICY_PATH}"}
    if repository == SOURCE_REPOSITORY:
        allowed_paths.update({POLICY_PATH, f"./{POLICY_PATH}"})
    if not any(
        reference.get("path", "").rsplit("@", 1)[0] in allowed_paths
        and reference.get("sha") == policy_sha
        for reference in run.get("referenced_workflows", [])
    ):
        errors.append("latest policy run did not use the current all/main policy commit")
    attempt = run["run_attempt"]
    jobs = list(client.pages(f"{run_path}/attempts/{attempt}/jobs", key="jobs"))
    policy_jobs = [job for job in jobs if job.get("name") == "all / check"]
    if len(policy_jobs) != 1 or any(
        job.get("status") != "completed" or job.get("conclusion") != "success"
        for job in policy_jobs
    ):
        errors.append("policy job all / check did not complete successfully")
    latest = client.get(run_path)
    if (latest.get("run_attempt"), latest.get("status"), latest.get("conclusion")) != (attempt, "completed", "success"):
        errors.append("policy run changed or is not successful")
    if _head(client, repository, branch) != head:
        errors.append("default branch changed during audit; rerun")
    return tuple(errors)


def audit(owner, *, token=None, inventory_token=None, client=None, now=None):
    client = client or GitHub(inventory_token or token)
    now = now or datetime.now(timezone.utc)
    results = []
    try:
        repositories, errors = _inventory(client, owner, bool(inventory_token))
        if errors:
            results.append(Result(f"{owner} (inventory)", errors))
        policy_sha = _head(client, SOURCE_REPOSITORY, "main")
    except (AuditError, AttributeError, KeyError, TypeError, ValueError) as error:
        return results + [Result(f"{owner} (audit)", (str(error),))]
    for repo in repositories:
        try:
            errors = _check_repository(client, repo, policy_sha, now)
        except (AuditError, AttributeError, KeyError, TypeError, ValueError) as error:
            errors = (str(error),)
        results.append(Result(repo["full_name"], errors))
    try:
        if _head(client, SOURCE_REPOSITORY, "main") != policy_sha:
            raise AuditError("all/main changed during audit; rerun")
    except (AuditError, AttributeError, KeyError, TypeError, ValueError) as error:
        results.append(Result(SOURCE_REPOSITORY, (str(error),)))
    return results
