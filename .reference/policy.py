"""Immutable remote Action references; explicit owner exceptions stay exact."""
from pathlib import Path
import re
import yaml

GIT_ACTION = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?@[0-9a-f]{40}\Z")


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    pairs = loader.construct_pairs(node, deep=deep)
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate workflow key: {key}")
        result[key] = value
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def assert_action_pins(root, workflows, *, exceptions=None):
    root = Path(root).resolve(strict=True)
    exceptions = {} if exceptions is None else exceptions
    if any(not isinstance(ref, str) or not isinstance(reason, str) or not reason.strip()
           for ref, reason in exceptions.items()):
        raise ValueError("each exact exception needs an owner reason")
    for name in workflows:
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError("workflow escapes checkout")
        workflow = yaml.load(path.read_bytes(), Loader=UniqueLoader)
        if not isinstance(workflow, dict) or not isinstance(workflow.get("jobs"), dict):
            raise ValueError("workflow requires jobs")
        for job_name, job in workflow["jobs"].items():
            if not isinstance(job, dict):
                raise ValueError("job must be a mapping")
            references = [job["uses"]] if "uses" in job else []
            steps = job.get("steps", [])
            if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
                raise ValueError("steps must be mappings")
            references += [step["uses"] for step in steps if "uses" in step]
            for ref in references:
                if not isinstance(ref, str):
                    raise ValueError("uses must be a string")
                if ref in exceptions:
                    continue
                if ref.startswith("docker://"):
                    continue  # Container references have a separate owner policy.
                if ref.startswith("./"):
                    local = (root / ref).resolve(strict=True)
                    if not local.is_relative_to(root):
                        raise AssertionError("local Action escapes checkout")
                elif not GIT_ACTION.fullmatch(ref):
                    raise AssertionError(f"{name}:{job_name}: mutable or unsupported action {ref}")
