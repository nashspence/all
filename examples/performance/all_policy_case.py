"""Sixteen real repository checks; an adoption example, not a reference timer."""
import json
from pathlib import Path
import sys

WORKFLOW = """name: all
on:
  push: {}
  pull_request: {}
  schedule:
    - cron: '17 3 * * *'
  workflow_dispatch: {}
permissions:
  contents: read
jobs:
  all:
    uses: nashspence/all/.github/workflows/policy.yml@main
"""
ERRORS = [[], [".github/workflows/all.yml: permissions must be contents: read"],
          [".github/workflows/all.yml: jobs must contain only an unconditional all job using "
           "nashspence/all/.github/workflows/policy.yml@main"],
          [".github/workflows/all.yml: missing or unreadable"]]


def prepare(subject, work):
    sys.dont_write_bytecode = True
    sys.path.insert(0, subject)
    from all_policy import check_repository
    roots = [Path(work) / "inputs" / str(i) for i in range(16)]
    for index, root in enumerate(roots):
        path = root / ".github/workflows/all.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        if index % 4 != 3:
            text = WORKFLOW
            if index % 4 == 1:
                text = text.replace("contents: read", "contents: write")
            if index % 4 == 2:
                text = text.replace("  all:\n", "  all:\n    if: false\n")
            path.write_text(text)
    return roots, check_repository


def run(context, repeat):
    roots, check = context
    return [list(check(root, "nashspence/example")) for root in roots]


def verify(context, value, repeat):
    return value == [ERRORS[index % 4] for index in range(16)]


def main():
    mode, subject, work = sys.argv[1:]
    output = Path(work) / "completed.json"
    if mode == "run":
        result = run(prepare(subject, work), 0)
        output.write_text(json.dumps(result))
    elif mode == "verify":
        if not verify(None, json.loads(output.read_text()), 0):
            raise RuntimeError("real check_repository output differs from the approved fixture oracle")
    else:
        raise ValueError("unknown case command")


if __name__ == "__main__":
    main()
