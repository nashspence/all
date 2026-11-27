"""Trusted outer timers for full commands and warm, completed API requests.

This is an ordinary reviewed-code gate, not a hostile-code sandbox. Keep the
shared runner, approval revision and required status outside candidate control.
The caller supplies storage paths explicitly; this module never mounts tmpfs or
substitutes it for native storage. A preflight rejection never earns a pass.
"""
import hashlib
import ctypes
from contextlib import nullcontext
import importlib.metadata
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import platform

from .allowances import FEATURES, validate_witness
from .contracts import REPETITIONS, _unique, evaluate
from .profiles import admit
from .approval import require_current

MAX_COHORT_SECONDS = 300
MAX_PHASE_SECONDS = 30


def source_info():
    files = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(Path(__file__).parent.glob("*.py"))}
    try:
        version = importlib.metadata.version("nashspence-all")
    except importlib.metadata.PackageNotFoundError:
        version = None
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"package": "nashspence-all", "module": "all_policy.performance",
            "version": version, "files_sha256": files, "package_sha256": digest,
            "python": platform.python_version(), "executable": sys.executable}


def _owned_children():
    try:
        return {int(pid) for pid in Path(f"/proc/self/task/{os.getpid()}/children").read_text().split()}
    except FileNotFoundError:
        # Some Linux environments omit the optional per-task children file.
        result = set()
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if int(fields[1]) == os.getpid():
                    result.add(int(entry.name))
            except (FileNotFoundError, ProcessLookupError):
                pass
        return result


def _kill_owned_children():
    # As a subreaper, this dedicated process adopts orphaned setsid descendants too.
    for _ in range(64):
        children = _owned_children()
        if not children:
            return
        for pid in children:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for pid in children:
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
    raise RuntimeError("operation descendants did not terminate")


class _ProcessScope:
    def __enter__(self):
        if len(list(Path("/proc/self/task").iterdir())) != 1 or _owned_children():
            raise RuntimeError("performance gate requires a dedicated single-threaded process")
        self.libc, self.previous = ctypes.CDLL(None, use_errno=True), ctypes.c_int()
        if self.libc.prctl(37, ctypes.byref(self.previous), 0, 0, 0) or self.libc.prctl(36, 1, 0, 0, 0):
            raise OSError(ctypes.get_errno(), "cannot own descendant lifecycle")
        return self

    def __exit__(self, *unused):
        try:
            _kill_owned_children()
        finally:
            self.libc.prctl(36, self.previous.value, 0, 0, 0)


def _remaining(deadline):
    seconds = min(MAX_PHASE_SECONDS, deadline - time.monotonic())
    if seconds <= 0:
        raise TimeoutError("fixed cohort deadline exhausted; no automatic retry")
    return seconds


def _environment(subject, work, features=None):
    # Preserve actual public runner identity so an approved adapter can inspect
    # the already-admitted protected storage pair. Never synthesize authority or
    # forward credentials; this context cannot approve a profile or budget.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "ImageOS", "ImageVersion",
           "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_SHA",
           "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME",
           "RUNNER_ENVIRONMENT", "RUNNER_OS", "RUNNER_NAME")
           if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", ALL_PERFORMANCE_SUBJECT=str(subject),
               ALL_PERFORMANCE_WORK=str(work))
    if features is not None:
        env["ALL_PERFORMANCE_FEATURES"] = json.dumps(
            {feature: feature in features for feature in FEATURES}, sort_keys=True)
    return env


def _stop(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()
    _kill_owned_children()


def _children_remain(process):
    for pid in _owned_children():
        try:
            if os.waitpid(pid, os.WNOHANG)[0] == 0:
                return True
        except ChildProcessError:
            pass
    try:
        os.killpg(process.pid, 0)
        return True
    except ProcessLookupError:
        return False


def _wait(process, deadline):
    # Linux pidfds avoid Popen.wait(timeout)'s polling sleeps entering short budgets.
    descriptor = os.pidfd_open(process.pid)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(descriptor, selectors.EVENT_READ)
            if not selector.select(_remaining(deadline)):
                raise TimeoutError("process deadline exceeded")
        return process.wait()
    finally:
        os.close(descriptor)


def _preflight(root, deadline):
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(Path(__file__).with_name("profiles.py")), str(root)],
            stdout=output, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            if _wait(process, deadline) != 0 or _children_remain(process):
                raise RuntimeError("shared preflight did not complete")
            output.seek(0)
            return json.loads(output.read(2 * 1024**2))
        finally:
            _stop(process)


def _command(argv, subject, work, deadline, repeat=0, features=None, witness=False):
    substitutions = dict(python=sys.executable, subject=str(subject), work=str(work), repeat=repeat)
    command = [argument.format_map(substitutions) for argument in argv]
    # Harness output must not add members to a candidate's measured directory.
    with (tempfile.TemporaryFile(dir=work.parent) as log,
          (tempfile.TemporaryFile(dir=work.parent) if witness else nullcontext(log)) as output):
        start = time.perf_counter_ns()
        process = subprocess.Popen(command, cwd=subject, env=_environment(subject, work, features),
                                   stdout=output, stderr=log, start_new_session=True)
        try:
            code = _wait(process, deadline)
            if code != 0 or _children_remain(process):
                raise RuntimeError(f"command did not complete cleanly (exit {code} or live descendants)")
            elapsed = time.perf_counter_ns() - start
            if witness:
                output.seek(0)
                data = output.read(65537)
                if len(data) > 65536:
                    raise ValueError("oversized feature witness")
                return json.loads(data, object_pairs_hook=_unique)
            return elapsed
        finally:
            _stop(process)


def _check_files(subject, binding):
    for relative, expected in binding.approved_files:
        path = (subject / relative).resolve()
        if not path.is_relative_to(subject) or not path.is_file():
            raise ValueError(f"approved file is missing or outside candidate: {relative}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected:
            raise ValueError(f"adapter/fixture/verifier change requires independent approval: {relative}")


class _Worker:
    def __init__(self, binding, subject, work, deadline):
        self.deadline, self.buffer = deadline, b""
        self.log = tempfile.TemporaryFile(dir=work.parent)
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-I", "-B", str(Path(__file__).with_name("worker.py")),
                 str(subject / binding.adapter), str(subject), str(work)],
                cwd=subject, env=_environment(subject, work, binding.features), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self.log, start_new_session=True)
        except Exception:
            self.log.close()
            raise
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)

    def receive(self, kind, repeat=None, witness=False):
        until = time.monotonic() + _remaining(self.deadline)
        while b"\n" not in self.buffer:
            seconds = until - time.monotonic()
            if seconds <= 0 or not self.selector.select(seconds):
                raise TimeoutError("worker response deadline exceeded")
            data = os.read(self.process.stdout.fileno(), 4096)
            if not data:
                raise RuntimeError("worker exited before completion or verification")
            self.buffer += data
            if len(self.buffer) > 65536:
                raise RuntimeError("oversized worker response")
        line, self.buffer = self.buffer.split(b"\n", 1)
        frame = json.loads(line, object_pairs_hook=_unique)
        if witness:
            if (not isinstance(frame, dict) or set(frame) != {"kind", "repeat", "witness"}
                    or frame["kind"] != kind or frame["repeat"] != repeat):
                raise RuntimeError("unexpected feature verification response")
            return frame["witness"]
        if frame != {"kind": kind, "repeat": repeat}:
            raise RuntimeError("unexpected worker response; timing/authority claims are not accepted")

    def send(self, kind, repeat=None):
        self.process.stdin.write(json.dumps(dict(kind=kind, repeat=repeat)).encode() + b"\n")
        self.process.stdin.flush()

    def close(self):
        self.selector.close()
        _stop(self.process)
        for stream in (self.process.stdin, self.process.stdout, self.log):
            try:
                stream.close()
            except OSError:
                pass


def _measure(binding, subject, work, deadline):
    observations, stages, worker = [], {}, None
    try:
        _check_files(subject, binding)
        if binding.mode == "request":
            start = time.perf_counter_ns()
            worker = _Worker(binding, subject, work, deadline)
            worker.receive("ready")
            stages["startup_ns"] = time.perf_counter_ns() - start
        for repeat in range(REPETITIONS):
            start = None
            row = {"elapsed_ns": None, "completed": False, "verified": False, "error": None}
            observations.append(row)
            try:
                if worker is None:
                    if binding.prepare:
                        row["prepare_ns"] = _command(binding.prepare, subject, work, deadline, repeat,
                                                     features=binding.features)
                    start = time.perf_counter_ns()
                    row["elapsed_ns"] = _command(binding.command, subject, work, deadline, repeat,
                                                 features=binding.features)
                else:
                    start = time.perf_counter_ns()
                    worker.send("run", repeat)
                    worker.receive("complete", repeat)
                    row["elapsed_ns"] = time.perf_counter_ns() - start
                row["completed"] = True
                verification_start = time.perf_counter_ns()
                if worker is None:
                    witness = _command(binding.verify, subject, work, deadline, repeat,
                                       features=binding.features, witness=binding.features is not None)
                else:
                    worker.send("verify", repeat)
                    witness = worker.receive("verified", repeat, witness=binding.features is not None)
                if binding.features is not None:
                    row["feature_witness"] = witness
                    validate_witness(binding.features, witness)
                row["verification_ns"] = time.perf_counter_ns() - verification_start
                row["verified"] = True
            except Exception as error:
                if row["elapsed_ns"] is None and start is not None:
                    row["elapsed_ns"] = time.perf_counter_ns() - start
                row["error"] = type(error).__name__ + ": " + str(error)
                if worker is not None or time.monotonic() >= deadline:
                    break
        if worker is not None:
            start = time.perf_counter_ns()
            worker.send("close")
            worker.receive("closed")
            _wait(worker.process, deadline)
            stages["drain_ns"] = time.perf_counter_ns() - start
            if worker.process.returncode != 0 or _children_remain(worker.process):
                raise RuntimeError("warm worker did not drain completely")
        _check_files(subject, binding)
    except Exception as error:
        stages["error"] = type(error).__name__ + ": " + str(error)
    finally:
        if worker is not None:
            worker.close()
    return observations, stages


def _candidate_revision(subject):
    revision = subprocess.check_output(
        ["git", "-C", str(subject), "rev-parse", "HEAD"], text=True, timeout=10).strip()
    subprocess.run(["git", "-C", str(subject), "diff", "--exit-code", "HEAD", "--"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    for ignored in (False, True):
        command = ["git", "-C", str(subject), "ls-files", "--others", "--exclude-standard"]
        if ignored:
            command.append("--ignored")
        if subprocess.check_output(command, timeout=10):
            raise ValueError("candidate contains unrecorded inputs; build artifacts belong outside the source checkout")
    return revision


def run_suite(authority, subject, storage_roots):
    """Accept only under current central approval, then own the complete lifecycle."""
    approval = require_current({limit.profile for limit in authority.limits.values()})
    with _ProcessScope():
        record = _run_suite(authority, subject, storage_roots)
    record["profile_approval"] = approval
    return record


def _run_suite(authority, subject, storage_roots):
    """One bounded cohort; every required operation runs three times, with no retry.

    storage_roots is a workflow-owned mapping from shared profile IDs to paths.
    It cannot grant a capability: actual mount metadata and probes determine it.
    """
    started = time.perf_counter_ns()
    deadline = time.monotonic() + MAX_COHORT_SECONDS
    subject = Path(subject).resolve()
    record = {"schema": 1, "authority_revision": authority.revision,
              "repository": authority.repository, "limits_sha256": authority.limits_sha256,
              "bindings_sha256": authority.bindings_sha256, "shared_source": source_info(),
              "preflights": {}, "operations": {}}
    try:
        record["candidate_revision"] = _candidate_revision(subject)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        record.update(verdict="failed", error=f"candidate must be a recorded clean Git checkout: {error}")
        return record
    # All preflights precede all candidate code. Later conditions cannot waive a miss.
    admitted_profiles = {}
    for profile in sorted({limit.profile for limit in authority.limits.values()}):
        root = None
        try:
            root = Path(storage_roots[profile]).resolve(strict=True)
            key = str(root)
            if key not in record["preflights"]:
                start = time.perf_counter_ns()
                record["preflights"][key] = _preflight(root, deadline)
                record["preflights"][key]["total_ns"] = time.perf_counter_ns() - start
        except (KeyError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            key = f"unavailable:{profile}"
            record["preflights"][key] = {"errors": [{"probe": "metadata", "error": str(error)}]}
        evidence = record["preflights"][key]
        admission = admit(profile, evidence)
        admitted_profiles[profile] = (root, admission)
    for profile, (root, admission) in admitted_profiles.items():
        for name, limit in authority.limits.items():
            if limit.profile != profile:
                continue
            binding = authority.bindings[name]
            observations, stages = [], {}
            if admission["admitted"]:
                try:
                    with tempfile.TemporaryDirectory(prefix="all-operation-", dir=root) as directory:
                        observations, stages = _measure(binding, subject, Path(directory), deadline)
                except Exception as error:
                    stages["error"] = type(error).__name__ + ": " + str(error)
            decision = evaluate(limit, admission, observations)
            if stages.get("error") and decision["verdict"] != "unqualified":
                decision["verdict"] = "failed"
            record["operations"][name] = dict(decision=decision, admission=admission,
                                              mode=binding.mode, unit=binding.unit,
                                              completion=binding.completion,
                                              observations=observations, excluded_stages=stages)
            if binding.features is not None:
                record["operations"][name]["features"] = list(binding.features)
    verdicts = {r["decision"]["verdict"] for r in record["operations"].values()}
    try:
        if _candidate_revision(subject) != record["candidate_revision"]:
            raise ValueError("candidate revision changed during measurement")
        if source_info() != record["shared_source"]:
            raise ValueError("shared qualification/clock/acceptance source changed during measurement")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        record["source_error"] = str(error)
        verdicts.add("failed")
    record["verdict"] = next(v for v in ("failed", "miss", "unqualified", "pass") if v in verdicts)
    record["total_ns"] = time.perf_counter_ns() - started
    return record
