"""Check immutable refs for direct remote GitHub Actions and reusable workflows."""

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

ROOT = Path(__file__).resolve().parents[1]
COMMIT = re.compile(r"[0-9a-fA-F]{40}")
REMOTE = re.compile(r"[\w.-]+/[\w.-]+(?:/[^@\s]+)?@([0-9a-zA-Z._/-]+)")
PROFFER_WORKFLOW = ".github/workflows/test.yml"
EXPECTED = {
    ("proffer", PROFFER_WORKFLOW, "test", "step", "actions/checkout@v4"): "nashspence/all#4",
    ("proffer", PROFFER_WORKFLOW, "test", "step", "actions/setup-python@v5"): "nashspence/all#4",
}


def git(root, *args):
    return subprocess.check_output(("git", *args), cwd=root)


def mapping(node):
    if not isinstance(node, MappingNode):
        raise ValueError("expected a mapping")
    result = {}
    for key, value in node.value:
        if not isinstance(key, ScalarNode):
            raise ValueError("expected a scalar mapping key")
        if key.value in result:
            raise ValueError(f"duplicate key: {key.value}")
        if key.value == "<<":
            raise ValueError("unexpected YAML merge key")
        result[key.value] = value
    return result


def workflow_uses(source):
    """Return (job, kind, 1-based line, ref) for direct remote references."""
    document = yaml.compose(source, Loader=yaml.BaseLoader)
    jobs = mapping(document).get("jobs")
    if jobs is None:
        raise ValueError("missing jobs")

    def check_uses(job_id, kind, uses):
        if not isinstance(uses, ScalarNode):
            raise ValueError(f"job {job_id}: expected a scalar {kind} uses reference")
        if not uses.value.startswith(("./", "docker://")):
            yield job_id, kind, uses.start_mark.line + 1, uses.value

    for job_id, job in mapping(jobs).items():
        fields = mapping(job)
        if "uses" in fields:
            yield from check_uses(job_id, "reusable workflow", fields["uses"])
        if "steps" not in fields:
            continue
        steps = fields["steps"]
        if not isinstance(steps, SequenceNode):
            raise ValueError(f"job {job_id}: expected a steps sequence")
        for step in steps.value:
            uses = mapping(step).get("uses")
            if uses is not None:
                yield from check_uses(job_id, "step", uses)


def full_sha(ref):
    match = REMOTE.fullmatch(ref)
    return match is not None and COMMIT.fullmatch(match[1]) is not None


def repo_workflows(repo, root, commit):
    for entry in git(root, "ls-tree", "-z", commit, ".github/workflows/").split(b"\0"):
        if not entry:
            continue
        metadata, workflow_bytes = entry.split(b"\t", 1)
        workflow = workflow_bytes.decode()
        if not workflow.endswith((".yaml", ".yml")):
            continue
        mode, kind, blob = metadata.decode().split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(f"{repo}/{workflow}: expected a regular workflow")
        yield repo, workflow, git(root, "cat-file", "blob", blob)


def workflows(root):
    """Read committed hub and checked-out submodule workflow blobs, not files."""
    yield from repo_workflows("all", root, "HEAD")
    for item in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not item:
            continue
        metadata, path_bytes = item.split(b"\t", 1)
        mode, commit, stage = metadata.decode().split()
        if mode != "160000":
            continue
        path = path_bytes.decode()
        if stage != "0" or not re.fullmatch(r"repos/[a-z0-9][a-z0-9._-]*", path):
            raise ValueError(f"unexpected gitlink: {path}")
        child = root / path
        if not (child / ".git").exists() or git(child, "rev-parse", "HEAD").decode().strip() != commit:
            raise ValueError(f"{path} is not checked out at {commit}")
        yield from repo_workflows(child.name, child, commit)


def check(sources, expected=EXPECTED):
    count = 0
    hits = Counter()
    errors = []
    notes = []
    for repo, workflow, source in sources:
        try:
            for job, kind, line, ref in workflow_uses(source):
                count += 1
                if full_sha(ref):
                    continue
                key = (repo, workflow, job, kind, ref)
                location = f"{repo}/{workflow}:{line} ({job}, {kind}): {ref}"
                if key in expected and not hits[key]:
                    hits[key] += 1
                    notes.append(f"XFAIL {location} [{expected[key]}]")
                else:
                    errors.append(f"FAIL {location}: expected a 40-character commit SHA")
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(f"FAIL {repo}/{workflow}: {exc}")
    for key in sorted(expected.keys() - hits.keys()):
        repo, workflow, job, kind, ref = key
        errors.append(f"XPASS {repo}/{workflow} ({job}, {kind}): {ref} [{expected[key]}]; remove stale exception")
    return count, notes, errors


def main():
    try:
        count, notes, errors = check(workflows(ROOT))
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    for note in notes:
        print(note)
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Checked {count} direct remote action and workflow references ({len(notes)} expected failures)")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
