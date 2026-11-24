"""Literal root Make command declarations; execution belongs to suite adapters."""

import re

ROLES = ("help", "setup", "test")


def _lines(source: str) -> list[str]:
    result, pending = [], ""
    for line in source.splitlines():
        if pending:
            line = pending + line.lstrip()
        if line.endswith("\\"):
            pending = line[:-1] + " "
            continue
        result.append(line)
        pending = ""
    if pending:
        raise ValueError("unterminated Make continuation")
    return result


def facade_errors(source: str | None) -> list[str]:
    if source is None:
        return ["root Makefile is missing"]
    lines = _lines(source)
    defaults, phony, targets = [], set(), {}
    current = ()
    for line in lines:
        if line.startswith("\t"):
            if line.strip():
                for target in current:
                    targets[target] = True
            continue
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        goal = re.fullmatch(r"\.DEFAULT_GOAL\s*(:=|=|\?=|\+=)\s*(.*)", line)
        if goal:
            defaults.append(goal.groups())
            current = ()
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.%-]+(?:\s+[A-Za-z0-9_.%-]+)*)\s*:(?!=)(.*)", line)
        if match is None:
            current = ()
            continue
        names, body = match.groups()
        current = tuple(names.split())
        if current == (".PHONY",):
            phony.update(body.split())
            current = ()
        else:
            for target in current:
                targets[target] = targets.get(target, False) or bool(body.strip())
    errors = []
    if defaults != [(":=", "help")]:
        errors.append("declare .DEFAULT_GOAL := help exactly once")
    for role in ROLES:
        if role not in phony:
            errors.append(f"{role}: missing explicit .PHONY declaration")
        if not targets.get(role, False):
            errors.append(f"{role}: missing executable target or prerequisite delegation")
    return errors
