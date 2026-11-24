from pathlib import PurePosixPath


INTERVALS = {"daily", "weekly", "monthly", "quarterly", "semiannually", "yearly", "cron"}


def surfaces(paths):
    result = set()
    names = {"uv.lock": "uv", "package-lock.json": "npm", "Dockerfile": "docker"}
    for raw in paths:
        if not isinstance(raw, str):
            raise ValueError("tracked paths must be strings")
        path = PurePosixPath(raw)
        if path.is_absolute() or path.as_posix() != raw or ".." in path.parts:
            raise ValueError("tracked paths must be canonical and relative")
        if path.name in names:
            directory = "/" if path.parent == PurePosixPath(".") else "/" + path.parent.as_posix()
            result.add((names[path.name], directory))
        elif path.parent == PurePosixPath(".github/workflows") and path.suffix in {".yml", ".yaml"}:
            result.add(("github-actions", "/"))
    return frozenset(result)


def _directory(value):
    if not isinstance(value, str) or not value.startswith("/"):
        raise ValueError("update directory must be absolute within the repository")
    path = PurePosixPath(value)
    if path.as_posix() != value or ".." in path.parts or any(c in value for c in "*?["):
        raise ValueError("owner adapter must resolve canonical exact update directories")
    return value


def update_routes(config, default_branch):
    if config is None:
        return frozenset()
    if not isinstance(config, dict) or type(config.get("version")) is not int or config["version"] != 2 or not isinstance(config.get("updates"), list):
        raise ValueError("expected a Dependabot version-2 updates mapping")
    routes = set()
    for entry in config["updates"]:
        if not isinstance(entry, dict):
            raise ValueError("update entries must be mappings")
        if entry.get("target-branch", default_branch) != default_branch:
            continue
        limit = entry.get("open-pull-requests-limit", 5)
        if type(limit) is not int or limit < 0:
            raise ValueError("invalid version-update pull request limit")
        if limit == 0:
            continue
        schedule = entry.get("schedule", {})
        if not isinstance(schedule, dict):
            raise ValueError("update schedule must be a mapping")
        interval = schedule.get("interval")
        cron = schedule.get("cronjob")
        if not isinstance(interval, str) or interval not in INTERVALS or (
            interval == "cron" and (not isinstance(cron, str) or not cron.strip())
        ):
            raise ValueError("a declared update schedule is required")
        if ("directory" in entry) == ("directories" in entry):
            raise ValueError("select directory or directories")
        directories = [entry["directory"]] if "directory" in entry else entry["directories"]
        if not isinstance(directories, list) or not directories:
            raise ValueError("update directories are required")
        ecosystem = entry.get("package-ecosystem")
        if not isinstance(ecosystem, str) or not ecosystem:
            raise ValueError("update ecosystem is required")
        for directory in directories:
            route = (ecosystem, _directory(directory))
            if route in routes:
                raise ValueError("overlapping update declarations")
            routes.add(route)
    return frozenset(routes)


def missing_updates(paths, config, *, default_branch="main", exceptions=None):
    required = surfaces(paths)
    exceptions = exceptions or {}
    if any(key not in required or not isinstance(reason, str) or not reason.strip()
           for key, reason in exceptions.items()):
        raise ValueError("exceptions must name current surfaces and an owner reason")
    return tuple(sorted(required - update_routes(config, default_branch) - exceptions.keys()))
