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

from posixpath import normpath

CATALOG = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "jdx/mise-action": "9e7f7633ff6f6d6048a9418a68d48f288f50eb14",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "github/codeql-action/init": "5595ccaf912efad79be6eef63a5619ff05969be3",
    "github/codeql-action/analyze": "5595ccaf912efad79be6eef63a5619ff05969be3",
}


def references(path, text):
    doc = load_yaml(text)
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        raise ValueError("workflow must contain jobs")
    result = {}
    for key, job in jobs.items():
        if not isinstance(job, dict):
            raise ValueError("job must be a mapping")
        if "uses" in job:
            result[f"{path}::jobs.{key}.uses"] = job["uses"]
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("steps must be a list")
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError("step must be a mapping")
            if "uses" in step:
                result[f"{path}::jobs.{key}.steps.{index}"] = step["uses"]
    if any(not isinstance(ref, str) for ref in result.values()):
        raise ValueError("uses must be text")
    return result


def check_workflows(files, deviations=None):
    deviations = {} if deviations is None else deviations
    problems = []
    seen = set()
    for path, text in files.items():
        try:
            refs = references(path, text)
        except ValueError as exc:
            problems.append(f"{path}: {exc}")
            continue
        for location, ref in refs.items():
            if ref.startswith(("./", "docker://")):
                continue
            action = normpath(ref.partition("@")[0]).casefold()
            if action not in CATALOG:
                continue
            seen.add(location)
            problems += difference(location, ref, f"{action}@{CATALOG[action]}", deviations)
    problems += [f"unknown action deviation: {key}" for key in deviations if key not in seen]
    return problems
