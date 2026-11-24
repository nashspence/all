import re
from pathlib import Path

import yaml

SOURCE_REPOSITORY = "nashspence/all"
WORKFLOW_PATH = ".github/workflows/all.yml"
POLICY_PATH = ".github/workflows/policy.yml"
POLICY_USES = f"{SOURCE_REPOSITORY}/{POLICY_PATH}@main"


class WorkflowLoader(yaml.SafeLoader):
    yaml_implicit_resolvers = {
        key: [(tag, pattern) for tag, pattern in values
              if tag != "tag:yaml.org,2002:bool"]
        for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise yaml.constructor.ConstructorError(
                    None, None, "workflow keys must be unique strings", key_node.start_mark
                )
            result[key] = self.construct_object(value_node, deep=deep)
        return result


WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.IGNORECASE), list("tTfF")
)


def check_workflow(text: str, repository: str = "") -> tuple[str, ...]:
    if len(text) > 65536:
        return (f"{WORKFLOW_PATH}: workflow exceeds 64 KiB",)
    try:
        workflow = yaml.load(text, Loader=WorkflowLoader)
    except (yaml.YAMLError, ValueError, RecursionError):
        return (f"{WORKFLOW_PATH}: invalid YAML",)
    if not isinstance(workflow, dict):
        return (f"{WORKFLOW_PATH}: expected a workflow mapping",)

    errors = []
    if set(workflow) != {"name", "on", "permissions", "jobs"}:
        errors.append("use only name, on, permissions, and jobs in the dedicated workflow")
    if not isinstance(workflow.get("name"), str) or not workflow["name"].strip():
        errors.append("name must be a nonempty string")
    events = workflow.get("on")
    required = {"push", "pull_request", "schedule", "workflow_dispatch"}
    if not isinstance(events, dict) or set(events) != required:
        errors.append("require push, pull_request, schedule, and workflow_dispatch")
    else:
        if any(events[event] not in ({}, None) for event in required - {"schedule"}):
            errors.append("push, pull_request, and workflow_dispatch must be unfiltered")
        schedule = events["schedule"]
        cron = (schedule[0].get("cron") if isinstance(schedule, list)
                and len(schedule) == 1 and isinstance(schedule[0], dict)
                and set(schedule[0]) == {"cron"} else None)
        if not isinstance(cron, str) or not re.fullmatch(
            r"(?:[0-9]|[1-5][0-9]) (?:[0-9]|1[0-9]|2[0-3]) \* \* \*", cron
        ):
            errors.append("schedule must contain one daily cron: minute hour * * *")
    if workflow.get("permissions") != {"contents": "read"}:
        errors.append("permissions must be contents: read")
    reference = f"./{POLICY_PATH}" if repository == SOURCE_REPOSITORY else POLICY_USES
    if workflow.get("jobs") != {"all": {"uses": reference}}:
        errors.append(f"jobs must contain only an unconditional all job using {reference}")
    return tuple(f"{WORKFLOW_PATH}: {error}" for error in errors)


def check_repository(path: str | Path, repository: str = "") -> tuple[str, ...]:
    try:
        text = (Path(path) / WORKFLOW_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return (f"{WORKFLOW_PATH}: missing or unreadable",)
    return check_workflow(text, repository)
