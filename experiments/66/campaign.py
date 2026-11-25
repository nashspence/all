"""Frozen #66 controller: retain every setup, admission and operation result."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_storage

BRANCH = "refs/heads/experiment/66-native-storage"
PROFILE = "public-linux-x64-4cpu-prepared-ext4-v1"


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def invoke(command, output, name, timeout):
    from all_policy.performance.runner import _ProcessScope, _stop
    start = time.perf_counter_ns()
    result = {"command": command, "timeout_seconds": timeout}
    with _ProcessScope(), (output / (name + ".stdout")).open("wb") as stdout, (output / (name + ".stderr")).open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            result["timed_out"] = True
        finally:
            _stop(child)
        result.update(returncode=child.returncode, outer_wall_ns=time.perf_counter_ns() - start)
    return result


def experimental_admit(evidence):
    """Explicit provisional profile; same generic probes, new fixed runtime."""
    from all_policy.performance.profiles import CAPS_NS
    reasons = []
    for phase in ("metadata", "metadata_after"):
        row = evidence.get(phase, {})
        mount = row.get("mount", {})
        checks = [
            (row.get("system") == "Linux", "Linux"),
            (row.get("machine") == "x86_64", "x86_64"),
            (row.get("python") == "3.12.16", "Python3.12.16"),
            (row.get("logical_cpus") == 4 and row.get("affinity_count") == 4, "four available CPUs"),
            (row.get("memory_total_bytes", 0) >= 14 * 1024**3, "14GiB memory"),
            (row.get("free_bytes", 0) >= 64 * 1024**2, "64MiB free"),
            (mount.get("fstype") == "ext4", "ext4"),
            (bool(row.get("topology")), "topology"),
        ]
        quota = row.get("cpu_max")
        if quota and not quota.startswith("max "):
            try:
                amount, period = map(int, quota.split())
                checks.append((period > 0 and amount >= 4 * period, "CPU quota"))
            except ValueError:
                checks.append((False, "CPU quota"))
        mem_max = row.get("memory_max")
        checks.append((mem_max in (None, "max") or str(mem_max).isdigit() and int(mem_max) >= 14 * 1024**3,
                       "memory quota"))
        reasons.extend(phase + ": " + message for ok, message in checks if not ok)
    before, after = evidence.get("metadata", {}), evidence.get("metadata_after", {})
    if any(before.get(k) != after.get(k) for k in ("root", "device", "mount")):
        reasons.append("mount identity changed")
    for name, cap in CAPS_NS.items():
        values = evidence.get("samples_ns", {}).get(name, [])
        if len(values) != 3 or any(type(v) is not int or not 0 < v <= cap for v in values):
            reasons.append(name + ": missing, invalid or over-cap observation")
    if evidence.get("errors"):
        reasons.append("generic preflight errors")
    return {"profile": PROFILE, "admitted": not reasons, "reasons": reasons,
            "scope": "experimental prepared native synchronization timing", "physical_persistence_proven": False}


def collect(args):
    from all_policy.performance import profiles
    output = Path(args.output).resolve()
    context = json.loads((output / "preparation.json").read_text())
    result = {"preflights": {}, "postflights": {}, "consumers": {}, "generic": None, "errors": []}
    record_path = output / "collection.json"
    def probe(key, phase):
        name = phase + "-" + key
        path = output / (name + ".json")
        call = invoke([sys.executable, "-I", "-B", str(Path(profiles.__file__)), context[key]],
                      output, name, 45)
        evidence = json.loads((output / (name + ".stdout")).read_text())
        evidence["command"] = call
        if call["returncode"] != 0 or call.get("timed_out"):
            evidence.setdefault("errors", []).append({"probe": "metadata", "error": "preflight command failed"})
        save(path, evidence)
        return experimental_admit(evidence)
    try:
        context = native_storage.verify(context, output / "preparation.json")
        save(output / "prepared-before.json", context)
        for key in ("root_loop_a", "root_loop_b"):
            result["preflights"][key] = probe(key, "preflight")
            save(record_path, result)
        if not all(v["admitted"] for v in result["preflights"].values()):
            result["errors"].append("one or both prepared roots failed prospective admission")
        else:
            generic_path = output / "generic.json"
            result["generic_command"] = invoke(
                [sys.executable, "-I", "-B", str(Path(__file__).with_name("measure_generic.py")),
                 "--root", context["root_loop_a"],
                 "--output", str(generic_path)], output, "generic", 100)
            if generic_path.exists():
                result["generic"] = json.loads(generic_path.read_text())
            save(record_path, result)
            for kind in ("riverhog", "fishhat"):
                record = output / (kind + ".json")
                python = getattr(args, kind + "_python")
                call = invoke([python, "-I", "-B", str(Path(__file__).with_name("measure_consumer.py")),
                    "--kind", kind, "--source", str(Path(args.workspace) / kind),
                    "--shared-source", str(Path(args.workspace) / "runtime"),
                    "--context", str(output / "preparation.json"),
                    "--output", str(record), "--work", str(output / (kind + "-work"))],
                    output, kind, 45)
                result["consumers"][kind] = {"command": call,
                    "result": json.loads(record.read_text()) if record.exists() else None}
                save(record_path, result)
        for key in ("root_loop_a", "root_loop_b"):
            result["postflights"][key] = probe(key, "postflight")
            save(record_path, result)
        if not all(v["admitted"] for v in result["postflights"].values()):
            result["errors"].append("one or both prepared roots failed frozen postflight")
        context = native_storage.verify(context, output / "preparation.json")
        save(output / "prepared-after.json", context)
        result["postflight_intact"] = True
    except Exception as error:
        result["errors"].append(type(error).__name__ + ": " + str(error))
    finally:
        save(record_path, result)
    return 0 if not result["errors"] else 1


def main(args):
    from all_policy.performance.runner import source_info
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    record = {"schema": 1, "campaign": os.environ.get("STORAGE66_PHASE"),
              "worker": os.environ.get("STORAGE66_WORKER"), "profile": PROFILE,
              "github": {k: os.environ.get(k) for k in ("GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
                  "GITHUB_REF", "GITHUB_SHA", "STORAGE66_WORKFLOW_SHA", "RUNNER_NAME", "ImageOS", "ImageVersion")},
              "python": platform.python_version(), "shared_source": source_info(), "errors": []}
    start = time.perf_counter_ns()
    context = None
    try:
        if platform.python_version() != "3.12.16":
            raise RuntimeError("exact Python3.12.16 required")
        if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
            raise RuntimeError("first attempts only")
        runtime = Path(args.workspace) / "runtime"
        source = subprocess.check_output(["git", "-c", "safe.directory=" + str(runtime), "-C", str(runtime),
                                          "rev-parse", "HEAD"], text=True).strip()
        if source != os.environ["FROZEN_SHARED_SHA"]:
            raise RuntimeError("runtime checkout does not match frozen source")
        expected = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((runtime / "all_policy/performance").glob("*.py"))}
        if record["shared_source"]["files_sha256"] != expected:
            raise RuntimeError("installed shared package differs from frozen source")
        record["source_revision"] = source
        if (output / "bootstrap.json").exists():
            record["bootstrap"] = json.loads((output / "bootstrap.json").read_text())
        phase_start = time.perf_counter_ns()
        try:
            context = native_storage.setup(expected_repository="nashspence/all", allowed_refs=[BRANCH],
                worker_id=record["worker"], report_path=output / "preparation.json", setup_timeout_s=180)
        finally:
            record["setup_outer_ns"] = time.perf_counter_ns() - phase_start
        save(output / "setup-complete.json", context)
        command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--collect",
                   "--workspace", args.workspace, "--output", str(output),
                   "--fishhat-python", args.fishhat_python, "--riverhog-python", args.riverhog_python]
        record["collection_command"] = invoke(command, output, "collection", 180)
        if (output / "collection.json").exists():
            record["collection"] = json.loads((output / "collection.json").read_text())
        context = json.loads((output / "preparation.json").read_text())
    except native_storage.PreparationError as error:
        context = error.context
        record["errors"].append(type(error).__name__ + ": " + str(error))
    except Exception as error:
        record["errors"].append(type(error).__name__ + ": " + str(error))
    finally:
        if context is not None:
            phase_start = time.perf_counter_ns()
            try:
                context = native_storage.cleanup(context, output / "preparation.json", cleanup_timeout_s=120)
            except native_storage.PreparationError as error:
                context = error.context
                record["errors"].append("cleanup: " + str(error))
            except Exception as error:
                record["errors"].append("cleanup: " + type(error).__name__ + ": " + str(error))
            finally:
                record["cleanup_outer_ns"] = time.perf_counter_ns() - phase_start
            record["preparation"] = context
            record["setup_cleanup_ns"] = record.get("setup_outer_ns", 0) + record["cleanup_outer_ns"]
            record["setup_cleanup_within_60s"] = record["setup_cleanup_ns"] <= 60_000_000_000 and context.get("status") == "cleaned"
        record["total_ns"] = time.perf_counter_ns() - start
        collected = record.get("collection", {})
        generic = collected.get("generic") or {}
        generic_rows = generic.get("operations", {})
        command = record.get("collection_command", {})
        resource_ok = (not record["errors"] and command.get("returncode") == 0
            and not command.get("timed_out") and not collected.get("errors")
            and collected.get("postflight_intact") is True
            and record.get("setup_cleanup_within_60s") is True
            and all(len(collected.get(phase, {})) == 2 and
                    all(v.get("admitted") is True for v in collected[phase].values())
                    for phase in ("preflights", "postflights"))
            and generic.get("complete") is True and len(generic_rows) == 8
            and all(v.get("decision", {}).get("verdict") == "pass" for v in generic_rows.values()))
        consumers = collected.get("consumers", {})
        consumer_ok = len(consumers) == 2 and all(
            v["command"].get("returncode") == 0 and not v["command"].get("timed_out")
            and (v.get("result") or {}).get("status") == "complete" for v in consumers.values())
        record["resource_screen"] = "pass" if resource_ok else "failed_or_incomplete"
        record["consumer_applicability"] = "both_completed_correctly" if consumer_ok else "not_established_for_both"
        record["profile_approved"] = False
        record["whole_worker_complete"] = bool(resource_ok and consumer_ok)
        save(output / "record.json", record)
        print("STORAGE66_RECORD " + json.dumps(record, sort_keys=True), flush=True)
    return 0 if record["whole_worker_complete"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true")
    for name in ("workspace", "output", "fishhat-python", "riverhog-python"):
        parser.add_argument("--" + name, required=True)
    options = parser.parse_args()
    raise SystemExit(collect(options) if options.collect else main(options))
