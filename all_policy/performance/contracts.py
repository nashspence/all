"""Reviewed limits and operation bindings, loaded from an approved Git object.

The required workflow, not the candidate, selects the approval revision. Reading
Git objects keeps worktree proposals inactive; it does not establish who approved
a commit. Repository review/protection remains the authority boundary.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
import re
import subprocess
from types import MappingProxyType

from .allowances import compile_limits
from .profiles import PROFILES

LIMITS_PATH = ".all/performance/limits.json"
BINDINGS_PATH = ".all/performance/bindings.json"
REPETITIONS = 3
MAX_OPERATIONS = 32


@dataclass(frozen=True)
class Limit:
    profile: str
    max_wall_ns: int


@dataclass(frozen=True)
class Binding:
    mode: str
    unit: str
    completion: str
    approved_files: tuple
    command: tuple = ()
    verify: tuple = ()
    prepare: tuple = ()
    adapter: str = ""
    cold_operation: str = ""
    features: tuple | None = None


@dataclass(frozen=True)
class Authority:
    revision: str
    repository: str
    limits_sha256: str
    bindings_sha256: str
    limits: object
    bindings: object


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _relative(path):
    return (isinstance(path, str) and bool(path)
            and not PurePosixPath(path).is_absolute()
            and ".." not in PurePosixPath(path).parts and "\\" not in path)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _command(value):
    _require(isinstance(value, list) and value and
             all(isinstance(v, str) and v and "\x00" not in v for v in value),
             "commands must be nonempty argument arrays")
    return tuple(value)


def _limits(document):
    _require(isinstance(document, dict) and set(document) == {"schema", "operations"}
             and type(document["schema"]) is int and document["schema"] in {1, 2},
             "invalid limits schema")
    declared = document["operations"]
    _require(isinstance(declared, dict) and 0 < len(declared) <= MAX_OPERATIONS,
             "bounded operation inventory required")
    rows, selections = {}, {}
    for name, row in declared.items():
        _require(isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", name),
                 "invalid operation id")
        _require(isinstance(row, dict), "invalid limit declaration")
        if document["schema"] == 2 and set(row) == {"profile", "core_ns", "optional_ns"}:
            expanded, features = compile_limits(name, **row)
            expanded = expanded["operations"]
        else:
            _require(set(row) == {"profile", "max_wall_ns"}, "invalid limit declaration")
            expanded, features = {name: row}, {}
        _require(not rows.keys() & expanded.keys(), "canonical operation ids collide")
        rows.update(expanded)
        selections.update(features)
        _require(len(rows) <= MAX_OPERATIONS, "expanded operation inventory exceeds 32 cases")
    return rows, selections


def load_authority(checkout, approved_revision, repository):
    """Load only previously approved objects; candidate manifests are never read."""
    _require(isinstance(approved_revision, str) and
             re.fullmatch(r"[0-9a-f]{40}", approved_revision), "full approved commit required")
    _require(isinstance(repository, str) and re.fullmatch(r"[^/]+/[^/]+", repository),
             "repository identity required")
    documents, digests = [], []
    for path in (LIMITS_PATH, BINDINGS_PATH):
        data = subprocess.check_output(
            ["git", "-C", str(checkout), "show", f"{approved_revision}:{path}"],
            stderr=subprocess.DEVNULL, timeout=10)
        _require(len(data) <= 262144, "authority document exceeds 256 KiB")
        documents.append(json.loads(data, object_pairs_hook=_unique))
        digests.append(hashlib.sha256(data).hexdigest())
    limits_doc, bindings_doc = documents
    rows, selections = _limits(limits_doc)
    _require(set(bindings_doc) == {"schema", "repository", "operations"}
             and bindings_doc["schema"] == 1 and bindings_doc["repository"] == repository,
             "invalid binding schema or repository")
    bindings = bindings_doc["operations"]
    _require(isinstance(rows, dict) and 0 < len(rows) <= MAX_OPERATIONS
             and isinstance(bindings, dict) and set(rows) == set(bindings),
             "every operation requires exactly one limit and approved binding")
    limits, operations = {}, {}
    for name, row in rows.items():
        _require(re.fullmatch(r"[a-z][a-z0-9_]{0,79}", name), "invalid operation id")
        _require(isinstance(row, dict) and set(row) == {"profile", "max_wall_ns"}
                 and isinstance(row["profile"], str) and row["profile"] in PROFILES
                 and type(row["max_wall_ns"]) is int
                 and row["max_wall_ns"] > 0, "limits contain only profile and positive raw nanoseconds")
        limits[name] = Limit(**row)
        spec = bindings[name]
        required = {"mode", "unit", "completion", "approved_files"}
        if name in selections:
            required.add("features")
        _require(isinstance(spec, dict) and required <= set(spec), "incomplete operation binding")
        mode = spec["mode"]
        allowed = required | ({"command", "verify", "prepare"} if mode == "command"
                              else {"adapter", "cold_operation"})
        _require(mode in {"command", "request"} and set(spec) <= allowed,
                 "unknown binding mode or authority override field")
        features = selections.get(name)
        if features is not None:
            _require(spec["features"] == list(features),
                     "binding must use the exact canonical feature selection")
        _require(all(isinstance(spec[k], str) and spec[k].strip() for k in ("unit", "completion")),
                 "unit and completed-operation boundary must be stated")
        files = spec["approved_files"]
        _require(isinstance(files, dict) and files and all(_relative(p) and
                 isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h) for p, h in files.items()),
                 "approved adapter, fixture and verifier hashes required")
        common = dict(mode=mode, unit=spec["unit"], completion=spec["completion"],
                      approved_files=tuple(sorted(files.items())), features=features)
        if mode == "command":
            operations[name] = Binding(**common, command=_command(spec.get("command")),
                                      verify=_command(spec.get("verify")),
                                      prepare=_command(spec["prepare"]) if "prepare" in spec else ())
        else:
            _require(spec.get("adapter") in files and spec.get("cold_operation") in rows,
                     "warm request requires an approved adapter and cold counterpart")
            operations[name] = Binding(**common, adapter=spec["adapter"],
                                      cold_operation=spec["cold_operation"])
    for name, binding in operations.items():
        if binding.mode == "request":
            _require(operations[binding.cold_operation].mode == "command",
                     "warm counterpart must measure a complete command")
            if binding.features is not None or operations[binding.cold_operation].features is not None:
                _require(operations[binding.cold_operation].features == binding.features
                         and limits[binding.cold_operation].profile == limits[name].profile,
                         "warm and cold counterparts require the same features and profile")
    return Authority(approved_revision, repository, *digests,
                     MappingProxyType(limits), MappingProxyType(operations))


def evaluate(limit, admission, observations):
    """Only raw parent-clock observations decide; all three must complete and fit."""
    raw = [o.get("elapsed_ns") for o in observations]
    valid_raw = [v for v in raw if type(v) is int and v > 0]
    over = [i for i, v in enumerate(raw) if type(v) is int and v > limit.max_wall_ns]
    result = {"verdict": "failed", "profile": limit.profile, "budget_ns": limit.max_wall_ns,
              "samples_ns": raw, "over_budget_indices": over,
              "raw_min_ns": min(valid_raw) if valid_raw else None,
              "raw_max_ns": max(valid_raw) if valid_raw else None,
              "raw_mean_ns": sum(valid_raw) / len(valid_raw) if valid_raw else None}
    if admission.get("admitted") is not True or admission.get("profile") != limit.profile:
        result["verdict"] = "unqualified"
    elif len(observations) == REPETITIONS and len(valid_raw) == REPETITIONS and all(
            o.get("completed") is True and o.get("verified") is True and not o.get("error")
            for o in observations):
        result["verdict"] = "miss" if over else "pass"
        result["miss_kind"] = ("all_over" if len(over) == REPETITIONS else "mixed") if over else None
    return result
