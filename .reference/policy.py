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


def check_independent_matrices(text, deviations=None):
    deviations = {} if deviations is None else deviations
    try:
        doc = load_yaml(text)
    except ValueError as exc:
        return [str(exc)]
    if not isinstance(doc.get("jobs"), dict):
        return ["workflow must contain jobs"]
    seen = set()
    problems = []
    for name, job in doc["jobs"].items():
        if not isinstance(job, dict):
            problems.append(f"{name}: invalid job")
            continue
        strategy = job.get("strategy")
        if strategy is not None and not isinstance(strategy, dict):
            problems.append(f"{name}: strategy must be a mapping")
            continue
        if strategy is None or "matrix" not in strategy:
            continue
        seen.add(name)
        problems += difference(name, strategy.get("fail-fast"), False, deviations)
    problems += [f"unknown matrix deviation: {key}" for key in deviations if key not in seen]
    return problems
