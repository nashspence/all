"""A small explicit EditorConfig shape; no general glob evaluator or file rewriter."""

import configparser
import re

PROFILE = {
    "*": {"charset": "utf-8", "end_of_line": "lf", "insert_final_newline": "true", "trim_trailing_whitespace": "true", "indent_style": "space"},
    "*.{json,py}": {"indent_size": "4"},
    "*.{yml,yaml}": {"indent_size": "2"},
    "*.{md,markdown}": {"trim_trailing_whitespace": "false"},
    "Makefile": {"indent_style": "tab"},
}
PROPERTIES = set().union(*(set(p) for p in PROFILE.values()))


def valid_property(key, value):
    if not isinstance(value, str):
        return False
    if value == "unset":
        return True
    choices = {
        "charset": {"latin1", "utf-8", "utf-8-bom", "utf-16be", "utf-16le"},
        "end_of_line": {"lf", "cr", "crlf"},
        "indent_style": {"space", "tab"},
        "insert_final_newline": {"true", "false"},
        "trim_trailing_whitespace": {"true", "false"},
    }
    if key == "indent_size":
        return value == "tab" or bool(re.fullmatch(r"[1-9][0-9]*", value))
    return value in choices.get(key, set())


def defaults_for(path):
    values = dict(PROFILE["*"])
    if path.endswith((".json", ".py")):
        values.update(PROFILE["*.{json,py}"])
    if path.endswith((".yml", ".yaml")):
        values.update(PROFILE["*.{yml,yaml}"])
    if path.endswith((".md", ".markdown")):
        values.update(PROFILE["*.{md,markdown}"])
    if path.split("/")[-1] == "Makefile":
        values.update(PROFILE["Makefile"])
    return values


def render(exceptions=None):
    lines = ["root = true"]
    sections = dict(PROFILE)
    for path, record in (exceptions or {}).items():
        sections["/" + path] = record["properties"]
    for section, values in sections.items():
        lines.extend(["", f"[{section}]"])
        lines.extend(f"{key} = {value}" for key, value in values.items())
    return "\n".join(lines) + "\n"


def check_config(text, tracked_paths, exceptions=None, nested_configs=()):
    """Exceptions are exact tracked file paths; their substantive reasons need review."""
    exceptions = {} if exceptions is None else exceptions
    errors = []
    if nested_configs:
        errors.append("nested EditorConfig files can shadow the shared root profile")
    expected = {"__root__": {"root": "true"}, **PROFILE}
    for path, record in exceptions.items():
        if (not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", path)
                or any(part in {".", ".."} for part in path.split("/")) or path not in tracked_paths):
            errors.append(f"exception must identify an exact current tracked path: {path}")
            continue
        if (not isinstance(record, dict) or set(record) != {"reason", "properties"}
                or not isinstance(record["reason"], str) or not record["reason"].strip()
                or not isinstance(record["properties"], dict) or not record["properties"]
                or not set(record["properties"]) <= PROPERTIES
                or not all(valid_property(k, v) for k, v in record["properties"].items())):
            errors.append(f"invalid reasoned properties for {path}")
            continue
        defaults = defaults_for(path)
        if all(defaults.get(k) == v for k, v in record["properties"].items()):
            errors.append(f"stale exception repeats shared defaults: {path}")
        expected["/" + path] = record["properties"]
    if not isinstance(text, str):
        return errors + ["missing root .editorconfig"]
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        parser.read_string("[__root__]\n" + text)
    except configparser.Error as exc:
        return errors + [f"invalid EditorConfig: {exc}"]
    if parser.defaults():
        errors.append("no inherited DEFAULT section")
    actual = {name: {key.lower(): value.lower() for key, value in parser.items(name)} for name in parser.sections()}
    if list(actual) != list(expected):
        errors.append("use the common section order, followed by exact file exceptions")
    for section in expected:
        if actual.get(section) != expected[section]:
            errors.append(f"[{section}]: shared properties or exact exception differ")
    return errors
