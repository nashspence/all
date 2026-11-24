"""Candidate source/command vocabulary for ordinary Python development."""
import tomllib
from typing import Mapping, Sequence


def source_errors(project: str | None, lock: str | None, authored_requirements: Sequence[str] = ()) -> list[str]:
    errors = []
    try:
        manifest = tomllib.loads(project or "")
        if not isinstance(manifest.get("dependency-groups", {}).get("dev"), list):
            errors.append("root pyproject.toml needs [dependency-groups].dev")
        if "dev-dependencies" in manifest.get("tool", {}).get("uv", {}):
            errors.append("legacy tool.uv.dev-dependencies is a second vocabulary")
    except (tomllib.TOMLDecodeError, AttributeError):
        errors.append("invalid root pyproject.toml")
    try:
        locked = tomllib.loads(lock or "")
        if type(locked.get("version")) is not int or locked["version"] != 1:
            errors.append("root uv.lock needs format version 1")
    except tomllib.TOMLDecodeError:
        errors.append("invalid root uv.lock")
    errors.extend(f"independent ordinary-development requirements source: {path}" for path in authored_requirements)
    return errors


def command_errors(commands: Mapping[str, Sequence[str]], *, workspace: bool, project_environment: str = ".venv") -> list[str]:
    """Check explicit argv bindings, not shell text or actual execution identity."""
    errors = []
    for role, argv in commands.items():
        if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence) or any(not isinstance(argument, str) or not argument.strip() for argument in argv):
            return [f"{role}: argv must be a sequence of nonempty strings"]
    prefix = ("mise", "exec", "--", "uv")
    scope = ("--all-packages",) if workspace else ()
    sync = prefix + ("sync", "--locked", "--group", "dev") + scope
    run = prefix + ("run", "--locked", "--group", "dev") + scope + ("--",)
    if tuple(commands.get("setup", ())) != sync:
        errors.append("ordinary setup must use the shared locked uv sync binding")
    test = tuple(commands.get("test", ()))
    if test[:len(run)] != run or len(test) == len(run):
        errors.append("ordinary test must use the shared locked uv run binding and a command")
    if project_environment != ".venv":
        errors.append("ordinary development environment must be the root .venv")
    return errors
