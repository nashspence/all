"""Verify each designated default-branch PR workflow runs its maintained test entrypoint."""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

from actions_pins import git, mapping, workflows

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Lane:
    workflow: str
    job: str
    command: str
    branch: str = "main"


def lane(filename, job, command):
    return Lane(f".github/workflows/{filename}.yml", job, command)


LANES = {
    "all": lane("submodules", "verify", "python3 checks/checkout_invariance.py"),
    "fishhat": lane(
        "ci", "unit-shards",
        'uv run --locked --all-packages --group dev --python "$FISHHAT_CI_PYTHON" '
        'python -m scripts.unit_shards run --index ${{ matrix.shard }}',
    ),
    "forgejo-restic-restore-bootstrap": lane("tests", "tests", "python -m pytest -q tests"),
    "guavajam": lane(
        "ci", "packages", "mise exec -- make test-${{ matrix.package }} PYTHON=.venv/bin/python",
    ),
    "press": lane("validate-source", "source", "make test"),
    "proffer": lane("test", "test", "python -m unittest discover -s tests -v"),
    "riverhog": lane(
        "ci", "units",
        'mise x -- uv run --locked --all-packages --group dev python scripts/ci_timing.py '
        'execute --workload "unit-$UNIT_SHARD" --run-id "${{ github.run_id }}-${{ github.run_attempt }}" '
        '--output "$RIVERHOG_CI_TIMING_DIR/receipt.json"',
    ),
}
EXCLUDED = frozenset({"0819870.xyz-public-keys"})  # Public-key data, no maintained tests.
EXPECTED_MISSING = {
    ("forgejo-restic-restore-bootstrap", LANES["forgejo-restic-restore-bootstrap"]): "nashspence/all#8",
}


def scalar(node):
    if not isinstance(node, ScalarNode):
        raise ValueError("expected a scalar")
    return node.value


def scalar_sequence(node):
    if not isinstance(node, SequenceNode):
        raise ValueError("expected a sequence")
    return [scalar(child) for child in node.value]


def branch_pattern(pattern, branch):
    # GitHub's documented filter subset: literal, *, ** and prefix !. Less
    # common filters must be reviewed rather than guessed by this narrow rule.
    if re.fullmatch(r"[A-Za-z0-9._/*-]+", pattern) is None:
        raise ValueError(f"review unsupported branch-filter pattern {pattern!r}")
    rx = "".join(".*" if part == "**" else "[^/]*" if part == "*" else re.escape(part)
                 for part in re.findall(r"\*\*|\*|.", pattern))
    return re.fullmatch(rx, branch) is not None


def covers_branch(config, branch):
    fields = mapping(config)
    if {"paths", "paths-ignore"} & fields.keys():
        raise ValueError("designated pull_request lane must not filter by changed paths")
    if "types" in fields and not {"opened", "reopened", "synchronize"} <= set(scalar_sequence(fields["types"])):
        raise ValueError("pull_request types must cover opened, reopened and synchronize")
    if "branches" in fields and "branches-ignore" in fields:
        raise ValueError("pull_request cannot have branches and branches-ignore together")
    if "branches-ignore" in fields:
        return not any(branch_pattern(pattern, branch)
                       for pattern in scalar_sequence(fields["branches-ignore"]))
    if "branches" not in fields:
        return True
    included = False
    for pattern in scalar_sequence(fields["branches"]):
        negative = pattern.startswith("!")
        if branch_pattern(pattern[1:] if negative else pattern, branch):
            included = not negative
    return included


def pr_trigger(document, branch):
    event = document.get("on")
    if isinstance(event, ScalarNode):
        return scalar(event) == "pull_request"
    if isinstance(event, SequenceNode):
        return "pull_request" in scalar_sequence(event)
    if isinstance(event, MappingNode):
        options = mapping(event).get("pull_request")
        if isinstance(options, MappingNode):
            return covers_branch(options, branch)
        if options is not None:
            if scalar(options) not in ("", "null", "Null", "NULL", "~"):
                raise ValueError("expected pull_request filter mapping or null")
            return True
    return False


def check_workflow(source, required):
    document = mapping(yaml.compose(source, Loader=yaml.BaseLoader))
    if not pr_trigger(document, required.branch):
        raise ValueError(f"no pull_request trigger covering {required.branch!r}")
    target = mapping(document.get("jobs")).get(required.job)
    if target is None:
        raise ValueError(f"missing job {required.job!r}")
    job = mapping(target)
    if "if" in job:
        raise ValueError(f"review condition on designated job {required.job!r}")
    steps = job.get("steps")
    if not isinstance(steps, SequenceNode):
        raise ValueError(f"job {required.job!r} needs a steps sequence")
    for node in steps.value:
        step = mapping(node)
        command = step.get("run")
        if command is not None and scalar(command).strip() == required.command:
            if "if" in step or "uses" in step:
                raise ValueError(f"designated step in {required.job!r} must be an unconditional run")
            return
    raise ValueError(f"job {required.job!r} must run {required.command!r}")


def check(repos, sources, lanes=LANES, excluded=EXCLUDED, expected=EXPECTED_MISSING):
    repos = set(repos)
    classified = set(lanes) | set(excluded)
    errors = [f"FAIL {repo}: unclassified repository" for repo in sorted(repos - classified)]
    errors += [f"FAIL {repo}: classified repository is not pinned" for repo in sorted(classified - repos)]
    present = {}
    designated = {(repo, requirement.workflow) for repo, requirement in lanes.items()}
    for repo, workflow, source in sources:
        key = (repo, workflow)
        if key not in designated:
            continue
        if key in present:
            errors.append(f"FAIL {repo}/{workflow}: duplicate workflow source")
        present[key] = source
    notes = []
    for repo in sorted(lanes.keys() & repos):
        required = lanes[repo]
        key = (repo, required)
        location = f"{repo}/{required.workflow}"
        source = present.get((repo, required.workflow))
        if source is None:
            if key in expected:
                notes.append(f"XFAIL {location} ({required.job}): designated workflow missing [{expected[key]}]")
            else:
                errors.append(f"FAIL {location}: designated workflow missing")
            continue
        try:
            check_workflow(source, required)
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(f"FAIL {location}: {exc}")
        else:
            if key in expected:
                errors.append(f"XPASS {location} ({required.job}) [{expected[key]}]; remove stale exception")
    return notes, errors


def inventory(root):
    yield "all"
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        metadata, filename = entry.split(b"\t", 1)
        mode, _, stage = metadata.split()
        if mode == b"160000":
            if stage != b"0" or re.fullmatch(rb"repos/[a-z0-9][a-z0-9._-]*", filename) is None:
                raise ValueError(f"unexpected gitlink: {filename!r}")
            yield filename.split(b"/", 1)[1].decode()


def main():
    try:
        notes, errors = check(inventory(ROOT), workflows(ROOT))
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    for note in notes:
        print(note)
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Checked {len(LANES)} designated PR test lanes ({len(notes)} expected failures)")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
