"""Project-relative src layout for the currently observed packaging dialects."""

from collections.abc import Mapping
from pathlib import PurePosixPath


def _path(value: str) -> bool:
    return isinstance(value, str) and bool(value) and "\\" not in value and str(PurePosixPath(value)) == value and not PurePosixPath(value).is_absolute() and not {".", ".."}.intersection(value.split("/"))


def layout_errors(metadata: Mapping, tracked: set[str]) -> list[str]:
    if "project" not in metadata:
        return []
    if any(not _path(path) for path in tracked):
        raise ValueError("tracked paths must be canonical project-relative paths")
    backend = metadata.get("build-system", {}).get("build-backend")
    tool = metadata.get("tool", {})
    errors = []
    if backend == "setuptools.build_meta":
        settings = tool.get("setuptools", {})
        packages = settings.get("packages", {})
        mapping = settings.get("package-dir", {})
        if isinstance(packages, dict):
            if packages.get("find", {}).get("where") != ["src"]:
                errors.append("setuptools discovery must use exactly src")
        else:
            errors.append("explicit setuptools package lists require a reviewed src-layout adapter")
        if "py-modules" in settings:
            errors.append("setuptools py-modules require a reviewed src-layout adapter")
        for name, location in mapping.items():
            if not _path(location) or not (location == "src" or location.startswith("src/")):
                errors.append(f"setuptools package-dir {name!r} escapes src")
    elif backend == "hatchling.build":
        build = tool.get("hatch", {}).get("build", {})
        wheel = build.get("targets", {}).get("wheel", {})
        packages = wheel.get("packages", [])
        if not isinstance(packages, list) or not packages:
            errors.append("declare Hatch wheel packages under src")
        else:
            for package in packages:
                if not _path(package) or not package.startswith("src/"):
                    errors.append(f"Hatch wheel package {package!r} is outside src")
                elif not any(path.startswith(package + "/") and path.endswith((".py", ".pyi")) for path in tracked):
                    errors.append(f"Hatch wheel package {package!r} has no tracked Python import sources")
        for key in ("sources", "force-include", "hooks", "only-include", "include"):
            if build.get(key) or wheel.get(key):
                errors.append(f"custom Hatch {key} requires a reviewed src-layout adapter")
    else:
        errors.append(f"unsupported backend {backend!r}: supply a reviewed src-layout adapter")
    sources = {path for path in tracked if path.startswith("src/") and path.endswith((".py", ".pyi"))}
    if not sources:
        errors.append("no tracked Python import sources under src")
    roots = {path.split("/")[1].split(".")[0] for path in sources}
    for root in roots:
        if any(path == root + ".py" or path.startswith(root + "/") for path in tracked):
            errors.append(f"flat source shadows src import root {root!r}")
    return errors
