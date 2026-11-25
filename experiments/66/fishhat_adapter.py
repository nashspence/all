"""Approved fishhat binding for the unchanged shared warm-request worker."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).parent))
import consumer_cases as cases


def _guard(work, phase, operation):
    try:
        return operation()
    except BaseException as error:
        (Path(work) / "consumer-error.json").write_text(json.dumps({
            "phase": phase, "type": type(error).__name__, "error": str(error),
            "traceback": traceback.format_exc()}, sort_keys=True) + "\n")
        raise


def _prepare(work):
    from all_policy.performance.prepared_storage import inspect

    roots = json.loads((work / "storage-context.json").read_text())
    prepared = inspect(roots["root_loop_a"])
    cases.require(prepared.get("errors") == [] and prepared.get("resource_roots") ==
                  {key: roots[key] for key in ("root_loop_a", "root_loop_b")},
                  "common inspector did not verify the trusted prepared resource tuple")
    context = cases.prepare("fishhat", roots["root_loop_a"], roots["root_loop_b"])
    context["evidence_work"] = work
    (work / "consumer-provenance.json").write_text(json.dumps({
        "kind": "fishhat", "fixture_id": context["id"], "path": str(context["path"]),
        "provenance": context["provenance"], "prepared_resource": prepared}, sort_keys=True) + "\n")
    return context


def prepare(subject, work):
    return _guard(work, "prepare", lambda: _prepare(Path(work)))


def run(context, repeat):
    return _guard(context["evidence_work"], "run", lambda: cases.run(context, repeat))


def _verify(context, result, repeat):
    checks = cases.verify(context, result, repeat)
    (context["evidence_work"] / f"verification-{repeat}.json").write_text(
        json.dumps(checks, sort_keys=True) + "\n")
    return checks["verified"] is True


def verify(context, result, repeat):
    return _guard(context["evidence_work"], "verify", lambda: _verify(context, result, repeat))


def close(context):
    _guard(context["evidence_work"], "close", lambda: cases.close(context))

