"""Reject owner-selected local backlog markers; GitHub owns work history.

This scans only selected maintained text. Product/test data can have exact-line
exceptions. History headings are owner supplied, not a global word blacklist.
"""
from pathlib import Path
import re

NOTE = re.compile(r"\b(?:TODO|FIXME)(?:\([^)\n]*\))?\s*:")


def assert_issue_owned_work(root, files, *, history_headings=(), allowed_lines=None):
    root = Path(root).resolve(strict=True)
    allowed_lines = {} if allowed_lines is None else allowed_lines
    files = set(files)
    if set(allowed_lines) - files:
        raise ValueError("exceptions must belong to selected files")
    expected = {(name, line) for name, lines in allowed_lines.items() for line in lines}
    used = set()
    headings = {value.casefold() for value in history_headings}
    violations = []
    for name in sorted(files):
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"selected file escapes checkout: {name}")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            heading = re.fullmatch(r"\s{0,3}#{1,6}\s+(.+?)\s*#*\s*", line)
            forbidden = bool(NOTE.search(line) or heading and heading[1].casefold() in headings)
            if forbidden:
                if (name, line) in expected:
                    used.add((name, line))
                else:
                    violations.append(f"{name}:{number}")
    if expected - used:
        raise AssertionError("unused exact-line data exceptions")
    if violations:
        raise AssertionError("work belongs in its issue: " + ", ".join(violations))
