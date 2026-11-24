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

PATH = ".github/workflows/ci.yml"


def check_workflows(files):
    problems = []
    documents = {}
    for path, text in files.items():
        try:
            documents[path] = load_yaml(text)
        except ValueError as exc:
            problems.append(f"{path}: {exc}")
    ci = documents.get(PATH)
    if ci is None:
        return problems + [f"missing {PATH}"]
    if ci.get("name") != "CI":
        problems.append(f"{PATH}: workflow name must be CI")
    named = [p for p, value in documents.items() if value.get("name") == "CI"]
    if named != [PATH]:
        problems.append("exactly the primary ci.yml must own the CI name")
    events = ci.get("on")
    if isinstance(events, str):
        events = [events]
    if not isinstance(events, (dict, list)):
        problems.append("primary CI must declare its events")
    else:
        for event in ("push", "pull_request", "workflow_dispatch"):
            if event not in events:
                problems.append(f"primary CI missing {event}")
    if not isinstance(ci.get("jobs"), dict) or not ci["jobs"]:
        problems.append("primary CI must contain jobs")
    return problems
