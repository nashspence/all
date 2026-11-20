"""Check the Press pilot's pinned, repo-owned parity test without loading it."""

import ast
import re
import subprocess
import sys

import yaml

from make_help import ROOT, git, inventory
from pr_ci import LANES, check_workflow

PRESS = LANES["press"]
TEST_FILE = "tests/test_press.py"
CLASS = "PublisherTests"
METHOD = "test_make_help_works_before_setup"
LOCATION = f"press/{TEST_FILE}::{CLASS}.{METHOD}"
EXPECTED_MISSING = None

SETUP_CONDITION = "ifneq ($(filter setup,$(MAKECMDGOALS)),)"
PYTHON = "PYTHON := mise exec -- uv run --locked python"
TEST_RECIPE = "\t@$(PYTHON) -m unittest discover -s tests"


def tracked_blob(pin, path):
    entries = git(pin.path, "ls-tree", "-z", pin.commit, "--", path).split(b"\0")
    if len(entries) != 2 or not entries[0]:
        raise ValueError(f"{path}: missing tracked file")
    metadata, name = entries[0].split(b"\t", 1)
    mode, kind, oid = metadata.split()
    if name != path.encode() or kind != b"blob" or mode not in {b"100644", b"100755"}:
        raise ValueError(f"{path}: expected a regular tracked blob")
    return git(pin.path, "cat-file", "blob", oid.decode())


def check_makefile(source):
    # Recognize the existing Press target shape, not arbitrary GNU Make
    # programs. Do not evaluate Make variables or includes in the hub.
    lines = source.decode().splitlines()
    active, targets, python = [], [], []
    for index, raw in enumerate(lines):
        if raw.startswith("\t"):
            continue
        line = raw.split("#", 1)[0].strip()
        if re.match(r"^(?:ifeq|ifneq|ifdef|ifndef|define)\s", line):
            active.append((line, False))
        elif line == "else" or line.startswith("else "):
            if not active or active[-1][1]:
                raise ValueError("Makefile: invalid conditional")
            condition, _ = active.pop()
            active.append((condition if line == "else" else line, True))
        elif line in {"endif", "endef"}:
            if not active:
                raise ValueError("Makefile: invalid conditional")
            active.pop()
        elif re.match(r"^(?:(?:override|export)\s+)*PYTHON\s*[+:?!]*=", line):
            python.append((line, list(active)))
        elif line.startswith(".IGNORE:"):
            ignored = line.partition(":")[2].split()
            if not ignored or "test" in ignored:
                raise ValueError("Makefile: test failures must not be ignored")
        elif ":" in line and "test" in line.split(":", 1)[0].split():
            targets.append((index, line, list(active)))
    if active:
        raise ValueError("Makefile: unclosed conditional")
    if python != [(PYTHON, [])]:
        raise ValueError("Makefile: expected the locked Python runner")
    if len(targets) != 1:
        raise ValueError("Makefile: expected one literal test target")
    index, target, context = targets[0]
    recipes = []
    for line in lines[index + 1:]:
        if line.startswith("\t"):
            recipes.append(line.rstrip())
        elif not line.strip() or line.lstrip().startswith("#"):
            continue
        else:
            break
    if target != "test:" or context not in ([], [(SETUP_CONDITION, True)]) or recipes != [TEST_RECIPE]:
        raise ValueError("Makefile: test must run unittest discovery in tests")


def test_present(source):
    module = ast.parse(source, filename=TEST_FILE)
    compile(module, TEST_FILE, "exec")  # Validate syntax without running any code.
    nodes = list(ast.walk(module))
    if not any(isinstance(node, ast.Import) and
               any(alias.name == "unittest" and alias.asname is None for alias in node.names)
               for node in module.body):
        raise ValueError(f"{TEST_FILE}: expected a direct unittest import")
    for node in nodes:
        if (isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
                and node.id in {"unittest", CLASS, "load_tests", METHOD, "__unittest_skip__"}):
            raise ValueError(f"{TEST_FILE}: test discovery name is rebound: {node.id}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "load_tests":
            raise ValueError(f"{TEST_FILE}: custom unittest discovery")

    classes = [node for node in nodes if isinstance(node, ast.ClassDef) and node.name == CLASS]
    if len(classes) != 1 or classes[0] not in module.body:
        raise ValueError(f"{TEST_FILE}: expected a single module-level {CLASS}")
    case = classes[0]
    if (case.decorator_list or case.keywords or len(case.bases) != 1
            or not isinstance(case.bases[0], ast.Attribute) or case.bases[0].attr != "TestCase"
            or not isinstance(case.bases[0].value, ast.Name) or case.bases[0].value.id != "unittest"):
        raise ValueError(f"{TEST_FILE}: {CLASS} must directly inherit undecorated unittest.TestCase")

    methods = [node for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == METHOD]
    if not methods:
        return False
    if len(methods) != 1 or methods[0] not in case.body or not isinstance(methods[0], ast.FunctionDef):
        raise ValueError(f"{TEST_FILE}: {METHOD} must be one direct synchronous method")
    test = methods[0]
    args = test.args
    if (test.decorator_list or [arg.arg for arg in args.posonlyargs + args.args] != ["self"]
            or args.vararg or args.kwarg or args.kwonlyargs or args.defaults):
        raise ValueError(f"{TEST_FILE}: {METHOD} must be undecorated and callable with self only")
    if any((isinstance(node, ast.Attribute) and node.attr in {"skipTest", "SkipTest"})
           or (isinstance(node, ast.Name) and node.id == "SkipTest")
           for node in ast.walk(test)):
        raise ValueError(f"{TEST_FILE}: {METHOD} must not skip")
    return True


def check(workflow, makefile, tests, expected=EXPECTED_MISSING):
    try:
        check_workflow(workflow, PRESS)
        check_makefile(makefile)
        present = test_present(tests)
    except (ValueError, SyntaxError, yaml.YAMLError) as exc:
        return [], [f"FAIL {LOCATION}: {str(exc)!r}"]
    if present and expected:
        return [], [f"XPASS {LOCATION} [{expected}]; remove the resolved exception"]
    if not present:
        if expected:
            return [f"XFAIL {LOCATION}: missing test method [{expected}]"], []
        return [], [f"FAIL {LOCATION}: missing test method"]
    return [], []


def main():
    try:
        press = next((pin for pin in inventory(ROOT) if pin.name == "press"), None)
        if press is None:
            raise ValueError("Press is not pinned")
        notes, errors = check(*(tracked_blob(press, path)
                                for path in (PRESS.workflow, "Makefile", TEST_FILE)))
    except (ValueError, subprocess.CalledProcessError) as exc:
        notes, errors = [], [f"FAIL {LOCATION}: {str(exc)!r}"]
    for note in notes:
        print(note)
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Checked Press repo-owned parity test ({len(notes)} expected failures)")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
