import json
import math
import re

import yaml


class JsonScalarLoader(yaml.SafeLoader):
    pass


REPLACED = {"tag:yaml.org,2002:" + name for name in ("bool", "int", "float", "timestamp")}
JsonScalarLoader.yaml_implicit_resolvers = {
    char: [(tag, pattern) for tag, pattern in resolvers if tag not in REPLACED]
    for char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
for name, pattern, first in (
    ("bool", r"(?:true|false)\Z", "tf"),
    ("int", r"-?(?:0|[1-9][0-9]*)\Z", "-0123456789"),
    ("float", r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+(?:[eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)\Z", "-0123456789"),
):
    JsonScalarLoader.add_implicit_resolver("tag:yaml.org,2002:" + name, re.compile(pattern), list(first))


def _number(loader, node):
    value = json.loads(loader.construct_scalar(node))
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite YAML number")
    return value


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key == "<<" or key in result:
            raise ValueError("duplicate, merge or non-string YAML key")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


for tag in ("int", "float"):
    JsonScalarLoader.add_constructor("tag:yaml.org,2002:" + tag, _number)
JsonScalarLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_json_scalars(source):
    for event in yaml.parse(source):
        if isinstance(event, yaml.events.AliasEvent) or getattr(event, "anchor", None) is not None:
            raise ValueError("YAML anchors and aliases require a separate owner profile")
        if getattr(event, "tag", None) is not None:
            raise ValueError("explicit YAML tags require a separate owner profile")
        if isinstance(event, yaml.events.DocumentStartEvent) and (event.version is not None or event.tags):
            raise ValueError("YAML directives require a separate owner profile")
    return yaml.load(source, Loader=JsonScalarLoader)
