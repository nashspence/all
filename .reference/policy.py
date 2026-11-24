"""A small policy reference; configuration checks are not execution evidence."""

import re
import yaml


class UniqueLoader(yaml.SafeLoader):
    pass


UniqueLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in entries
          if tag != "tag:yaml.org,2002:bool"]
    for key, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"))


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result or key == "<<":
            raise ValueError("ambiguous YAML mapping")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueLoader.add_constructor("tag:yaml.org,2002:map", _mapping)


def _acyclic(value, active=None):
    active = set() if active is None else active
    if not isinstance(value, (dict, list)):
        return
    identity = id(value)
    if identity in active:
        raise ValueError("recursive YAML aliases are invalid")
    active.add(identity)
    for child in (value.values() if isinstance(value, dict) else value):
        _acyclic(child, active)
    active.remove(identity)


def load_yaml(text):
    try:
        value = yaml.load(text, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise ValueError("invalid YAML") from exc
    if not isinstance(value, dict):
        raise ValueError("expected a mapping")
    _acyclic(value)
    return value


def same(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


def difference(location, actual, expected, deviations):
    if same(actual, expected):
        return [f"{location}: stale deviation"] if location in deviations else []
    rule = deviations.get(location)
    if (isinstance(rule, dict)
            and set(rule) == {"observed", "reason", "revisit_when"}
            and same(rule["observed"], actual)
            and all(isinstance(rule[k], str) and rule[k].strip()
                    for k in ("reason", "revisit_when"))):
        return []
    return [f"{location}: expected {expected!r}; observed {actual!r}"]

import json

FIELDS = ("schedule", "open-pull-requests-limit", "groups", "assignees", "commit-message")


def profile(owner):
    return {
        "schedule": {"interval": "weekly", "day": "monday", "time": "04:00", "timezone": "Etc/UTC"},
        "open-pull-requests-limit": 1,
        "groups": {
            "version-updates": {"applies-to": "version-updates", "patterns": ["*"]},
            "security-updates": {"applies-to": "security-updates", "patterns": ["*"]},
        },
        "assignees": [owner],
        "commit-message": {"prefix": "deps"},
    }


def route_key(route):
    if not isinstance(route, dict) or not isinstance(route.get("package-ecosystem"), str):
        raise ValueError("invalid update route")
    if ("directory" in route) == ("directories" in route):
        raise ValueError("route needs exactly one directory selector")
    paths = [route["directory"]] if "directory" in route else route["directories"]
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or not p.startswith("/") for p in paths):
        raise ValueError("invalid route directories")
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate route directories")
    return json.dumps([route["package-ecosystem"], sorted(paths), route.get("target-branch", "<default>")], separators=(",", ":"))


def check_updates(text, owner="nashspence", deviations=None):
    deviations = {} if deviations is None else deviations
    if not isinstance(owner, str) or not owner.strip():
        return ["owner must be explicit"]
    try:
        doc = load_yaml(text)
    except ValueError as exc:
        return [str(exc)]
    routes = doc.get("updates")
    if not same(doc.get("version"), 2) or not isinstance(routes, list) or not routes:
        return ["expected nonempty Dependabot v2 updates"]
    problems = []
    seen = set()
    for route in routes:
        try:
            key = route_key(route)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if key in seen:
            problems.append(f"{key}: duplicate route")
        seen.add(key)
        observed = {k: route.get(k) for k in FIELDS}
        problems += difference(key, observed, profile(owner), deviations)
    problems += [f"unknown route deviation: {key}" for key in deviations if key not in seen]
    return problems
