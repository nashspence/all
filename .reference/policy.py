"""Check owner-classified read-only jobs; this is not a workflow trust analyzer."""

import re
from collections.abc import Mapping


def load_workflow(source: str) -> dict:
    """Use the repository's PyYAML dependency; reject duplicate/merge keys and aliases."""
    import yaml
    from yaml.nodes import MappingNode, ScalarNode, SequenceNode

    if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)) for token in yaml.scan(source)):
        raise ValueError("workflow aliases are outside this strict adapter")

    def convert(node):
        if isinstance(node, ScalarNode) and node.tag == "tag:yaml.org,2002:str":
            return node.value
        if isinstance(node, SequenceNode):
            return [convert(child) for child in node.value]
        if isinstance(node, MappingNode):
            result = {}
            for key, value in node.value:
                if not isinstance(key, ScalarNode):
                    raise ValueError("workflow mapping key must be scalar")
                name = convert(key)
                if name == "<<" or name in result:
                    raise ValueError("duplicate or merge workflow key")
                result[name] = convert(value)
            return result
        raise ValueError("unsupported workflow node or explicit tag")

    result = convert(yaml.compose(source, Loader=yaml.BaseLoader))
    if not isinstance(result, dict):
        raise ValueError("workflow must be a mapping")
    return result


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            yield from _strings(key)
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def check_read_only_jobs(
    workflow: Mapping,
    expected_permissions: Mapping[str, Mapping[str, str]],
    prohibited_secret_names: frozenset[str],
) -> None:
    """Local adapters own job classification and the list of publication credentials.

    Direct dot/bracket secret references are checked; expressions, reusable workflow
    trust and arbitrary commands require their owning workflow review.
    """
    jobs = workflow.get("jobs")
    if not isinstance(jobs, Mapping):
        raise ValueError("workflow has no jobs mapping")
    secret_refs = re.compile(r"\bsecrets\s*(?:\.\s*([A-Za-z_][A-Za-z0-9_]*)|\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\])", re.IGNORECASE)
    prohibited = {name.casefold() for name in prohibited_secret_names}
    for name, expected in expected_permissions.items():
        if not isinstance(expected, Mapping) or any(value not in {"read", "none"} for value in expected.values()):
            raise ValueError("owner-classified job requires explicit read/none permissions")
        job = jobs.get(name)
        if not isinstance(job, Mapping):
            raise ValueError("owner-classified job is missing")
        effective = job.get("permissions", workflow.get("permissions"))
        if not isinstance(effective, Mapping) or dict(effective) != dict(expected):
            raise ValueError(f"permissions differ from the read-only job declaration: {name}")
        if job.get("secrets") == "inherit":
            raise ValueError("read-only validation cannot inherit an unknown secret set")
        for text in _strings([workflow.get("env", {}), workflow.get("defaults", {}), job]):
            if any((match.group(1) or match.group(2)).casefold() in prohibited for match in secret_refs.finditer(text)):
                raise ValueError("read-only validation references a prohibited publication credential")
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("job steps must be a sequence")
        for step in steps:
            if not isinstance(step, Mapping):
                raise ValueError("job step must be a mapping")
            uses = step.get("uses", "")
            if not isinstance(uses, str):
                raise ValueError("step action must be a literal reference")
            if uses.lower().startswith("actions/checkout@"):
                parameters = step.get("with", {})
                persist = parameters.get("persist-credentials") if isinstance(parameters, Mapping) else None
                if not (persist is False or type(persist) is str and persist == "false"):
                    raise ValueError("checkout retains credentials in a read-only job")

