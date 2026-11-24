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

EXPECTED = "ubuntu-24.04"


def check_linux_runners(runners, deviations=None):
    deviations = {} if deviations is None else deviations
    if not isinstance(runners, dict):
        return ["the Linux lane inventory must be a mapping"]
    problems = []
    for location, actual in runners.items():
        problems += difference(location, actual, EXPECTED, deviations)
    problems += [f"unknown runner deviation: {key}" for key in deviations if key not in runners]
    return problems


def declared_ubuntu_lanes(text):
    doc = load_yaml(text)
    if not isinstance(doc.get("jobs"), dict):
        raise ValueError("workflow must contain jobs")
    result = {}
    for key, job in doc["jobs"].items():
        if not isinstance(job, dict):
            raise ValueError("job must be a mapping")
        runner = job.get("runs-on")
        if isinstance(runner, str) and runner.casefold().startswith("ubuntu-"):
            result[key] = runner
        elif runner == "${{ matrix.os }}":
            matrix = job.get("strategy", {}).get("matrix")
            if not isinstance(matrix, dict) or not isinstance(matrix.get("os"), list):
                raise ValueError(f"{key}: unresolved OS matrix; supply an owner-resolved lane inventory")
            for index, os_name in enumerate(matrix["os"]):
                if isinstance(os_name, str) and os_name.casefold().startswith("ubuntu-"):
                    result[f"{key}.matrix.os[{index}]"] = os_name
            for index, row in enumerate(matrix.get("include", [])):
                if isinstance(row, dict) and isinstance(row.get("os"), str) and row["os"].casefold().startswith("ubuntu-"):
                    result[f"{key}.matrix.include[{index}].os"] = row["os"]
    return result
