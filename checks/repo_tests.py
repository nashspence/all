"""Check pinned repo-owned parity tests without loading downstream code."""

import ast
import re
import subprocess
import sys
from dataclasses import dataclass

import yaml

from make_help import ROOT, git, inventory
from pr_ci import LANES, Lane, check_workflow

SETUP_CONDITION = "ifneq ($(filter setup,$(MAKECMDGOALS)),)"


@dataclass(frozen=True)
class RepoTest:
    repo: str
    lane: Lane
    target: str
    directory: str
    filename: str
    case: str
    method: str
    python: str
    flags: str = ""
    condition: tuple = ()

    @property
    def path(self):
        return f"{self.directory}/{self.filename}"

    @property
    def location(self):
        return f"{self.repo}/{self.path}::{self.case}.{self.method}"

    @property
    def recipe(self):
        return f"\t@$(PYTHON) -m unittest discover -s {self.directory}{self.flags}"


PRESS = RepoTest(
    "press", LANES["press"], "test", "tests", "test_press.py",
    "PublisherTests", "test_make_help_works_before_setup",
    "PYTHON := mise exec -- uv run --locked python",
    condition=((SETUP_CONDITION, True),),
)
GUAVAJAM = RepoTest(
    "guavajam", Lane(LANES["guavajam"].workflow, LANES["guavajam"].job,
                    "make test-repository PYTHON=.venv/bin/python", LANES["guavajam"].branch),
    "test-repository", "tests/repository", "test_renderer_checkout.py",
    "RendererCheckoutTests", "test_javascript_fingerprint_inputs_keep_checkout_bytes",
    "PYTHON := mise exec -- uv run --locked --all-packages --group dev python",
    flags=" -v",
)
PROBES = (PRESS, GUAVAJAM)
EXPECTED_MISSING = {GUAVAJAM: "nashspence/all#18"}


def tracked_blob(pin, path, *, missing_ok=False):
    entries = git(pin.path, "ls-tree", "-z", pin.commit, "--", path).split(b"\0")
    if entries == [b""] and missing_ok:
        return None
    if len(entries) != 2 or not entries[0]:
        raise ValueError(f"{path}: missing tracked file")
    metadata, name = entries[0].split(b"\t", 1)
    mode, kind, oid = metadata.split()
    if name != path.encode() or kind != b"blob" or mode not in {b"100644", b"100755"}:
        raise ValueError(f"{path}: expected a regular tracked blob")
    return git(pin.path, "cat-file", "blob", oid.decode())


def check_makefile(probe, source):
    # Recognize the existing test target shape, not arbitrary GNU Make
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
            if not ignored or probe.target in ignored:
                raise ValueError("Makefile: test failures must not be ignored")
        elif ":" in line and probe.target in line.split(":", 1)[0].split():
            targets.append((index, line, list(active)))
    if active:
        raise ValueError("Makefile: unclosed conditional")
    if python != [(probe.python, [])]:
        raise ValueError("Makefile: expected the locked Python runner")
    if len(targets) != 1:
        raise ValueError(f"Makefile: expected one literal {probe.target} target")
    index, target, context = targets[0]
    recipes = []
    for line in lines[index + 1:]:
        if line.startswith("\t"):
            recipes.append(line.rstrip())
        elif not line.strip() or line.lstrip().startswith("#"):
            continue
        else:
            break
    if (target != f"{probe.target}:" or tuple(context) not in ((), probe.condition)
            or recipes != [probe.recipe]):
        raise ValueError(f"Makefile: {probe.target} must run unittest discovery in {probe.directory}")


def test_present(probe, source):
    path, case_name, method_name = probe.path, probe.case, probe.method
    module = ast.parse(source, filename=path)
    compile(module, path, "exec")  # Validate syntax without running any code.
    nodes = list(ast.walk(module))
    if not any(isinstance(node, ast.Import) and
               any(alias.name == "unittest" and alias.asname is None for alias in node.names)
               for node in module.body):
        raise ValueError(f"{path}: expected a direct unittest import")
    for node in nodes:
        if (isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
                and node.id in {"unittest", case_name, "load_tests", method_name, "__unittest_skip__"}):
            raise ValueError(f"{path}: test discovery name is rebound: {node.id}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "load_tests":
            raise ValueError(f"{path}: custom unittest discovery")

    classes = [node for node in nodes if isinstance(node, ast.ClassDef) and node.name == case_name]
    if len(classes) != 1 or classes[0] not in module.body:
        raise ValueError(f"{path}: expected a single module-level {case_name}")
    case = classes[0]
    if (case.decorator_list or case.keywords or len(case.bases) != 1
            or not isinstance(case.bases[0], ast.Attribute) or case.bases[0].attr != "TestCase"
            or not isinstance(case.bases[0].value, ast.Name) or case.bases[0].value.id != "unittest"):
        raise ValueError(f"{path}: {case_name} must directly inherit undecorated unittest.TestCase")

    methods = [node for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == method_name]
    if not methods:
        return False
    if len(methods) != 1 or methods[0] not in case.body or not isinstance(methods[0], ast.FunctionDef):
        raise ValueError(f"{path}: {method_name} must be one direct synchronous method")
    test = methods[0]
    args = test.args
    if (test.decorator_list or [arg.arg for arg in args.posonlyargs + args.args] != ["self"]
            or args.vararg or args.kwarg or args.kwonlyargs or args.defaults):
        raise ValueError(f"{path}: {method_name} must be undecorated and callable with self only")
    if any((isinstance(node, ast.Attribute) and node.attr in {"skipTest", "SkipTest"})
           or (isinstance(node, ast.Name) and node.id == "SkipTest")
           for node in ast.walk(test)):
        raise ValueError(f"{path}: {method_name} must not skip")
    return True


def check(probe, workflow, makefile, tests, expected=None):
    location = probe.location
    try:
        check_workflow(workflow, probe.lane)
        check_makefile(probe, makefile)
        present = tests is not None and test_present(probe, tests)
    except (ValueError, SyntaxError, yaml.YAMLError) as exc:
        return [], [f"FAIL {location}: {str(exc)!r}"]
    if present and expected:
        return [], [f"XPASS {location} [{expected}]; remove the resolved exception"]
    if not present:
        reason = "missing tracked test file" if tests is None else "missing test method"
        if expected:
            return [f"XFAIL {location}: {reason} [{expected}]"], []
        return [], [f"FAIL {location}: {reason}"]
    return [], []


def main():
    notes, errors = [], []
    try:
        pins = {pin.name: pin for pin in inventory(ROOT)}
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL {str(exc)!r}", file=sys.stderr)
        return 1
    for probe in PROBES:
        try:
            if probe.repo not in pins:
                raise ValueError(f"{probe.repo} is not pinned")
            pin = pins[probe.repo]
            found, failed = check(
                probe, tracked_blob(pin, probe.lane.workflow), tracked_blob(pin, "Makefile"),
                tracked_blob(pin, probe.path, missing_ok=True), EXPECTED_MISSING.get(probe),
            )
            notes.extend(found)
            errors.extend(failed)
        except (ValueError, subprocess.CalledProcessError) as exc:
            errors.append(f"FAIL {probe.location}: {str(exc)!r}")
    for note in notes:
        print(note)
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Checked {len(PROBES)} repo-owned parity tests ({len(notes)} expected failures)")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
