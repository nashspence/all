"""Finite profile approval from reviewed enrollment and retained first attempts.

The trusted publisher classifies raw evidence. This evaluator never turns an
unknown allocation into an environmental rejection or retries a failed run.
"""
from datetime import datetime, timedelta
import re

from .profiles import CORE, PREPARED_EXT4


FRESHNESS = timedelta(days=10)
PENDING_ALLOWANCE = timedelta(hours=2)
LIVE_WINDOW = timedelta(days=30)
# Reserve room for fresh qualification before the Contents API encoding limit.
INDEX_WARNING_BYTES = 256 * 1024
MAX_ACTIVE_INDEX_BYTES = 512 * 1024
MAX_INDEX_BYTES = 768 * 1024
WORKFLOWS = {
    CORE: ".github/workflows/core-profile-refresh.yml",
    PREPARED_EXT4: ".github/workflows/storage-profile-refresh.yml",
}
EVENTS = {"push", "schedule", "workflow_dispatch"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, names, label):
    _require(isinstance(value, dict) and set(value) == set(names.split()),
             f"invalid {label} fields")


def _integer(value, minimum=1):
    return type(value) is int and value >= minimum


def _hex(value, length):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def _time(value):
    _require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value) is not None,
        "timestamps must be UTC RFC3339 strings ending Z")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _format(value):
    return value.isoformat().replace("+00:00", "Z")


def validate_registry(registry):
    _keys(registry, "schema profiles", "registry")
    _require(type(registry["schema"]) is int and registry["schema"] == 1 and
             isinstance(registry["profiles"], dict), "invalid registry schema")
    for profile, entry in registry["profiles"].items():
        _require(profile in WORKFLOWS, "unsupported enrolled profile")
        _keys(entry, "source_commit source_digest workflow workflow_digest qualification_runs disposition", "enrollment")
        _require(_hex(entry["source_commit"], 40) and _hex(entry["source_digest"], 64) and
                 _hex(entry["workflow_digest"], 64), "invalid enrollment identity")
        _require(entry["workflow"] == WORKFLOWS[profile], "profile/workflow mismatch")
        runs = entry["qualification_runs"]
        _require(isinstance(runs, list) and 1 <= len(runs) <= (2 if profile == CORE else 1)
                 and all(_integer(run) for run in runs) and len(set(runs)) == len(runs),
                 "invalid qualification run inventory")
        disposition = entry["disposition"]
        _keys(disposition, "url reason", "disposition")
        _require(isinstance(disposition["url"], str) and re.fullmatch(
            r"https://github\.com/nashspence/all/(?:issues|pull)/[1-9][0-9]*(?:#[A-Za-z0-9_-]+)?",
            disposition["url"]) is not None and isinstance(disposition["reason"], str)
            and bool(disposition["reason"].strip()), "reviewed disposition required")
    return registry


def validate_index(index):
    _keys(index, "schema runs", "evidence index")
    _require(type(index["schema"]) is int and index["schema"] == 1 and
             isinstance(index["runs"], list), "invalid evidence index schema")
    ids = set()
    for run in index["runs"]:
        _keys(run, "run_id workflow source_commit source_digest workflow_digest run_attempt event ref "
              "created_at started_at completed_at cohorts evidence_path evidence_sha256", "run")
        identity = run["run_id"]
        _require(_integer(identity) and identity not in ids, "duplicate or invalid run ID")
        ids.add(identity)
        _require(run["workflow"] in WORKFLOWS.values() and _hex(run["source_commit"], 40)
                 and _hex(run["source_digest"], 64) and _hex(run["workflow_digest"], 64)
                 and _hex(run["evidence_sha256"], 64), "invalid run identity")
        _require(type(run["run_attempt"]) is int and run["run_attempt"] == 1 and
                 isinstance(run["event"], str) and run["event"] in EVENTS and run["ref"] == "refs/heads/main",
                 "only original main-branch allocations are evidence")
        _require(run["evidence_path"] == f"runs/{identity}.json", "invalid raw evidence path")
        created, completed = _time(run["created_at"]), _time(run["completed_at"])
        started = created if run["started_at"] is None else _time(run["started_at"])
        _require(created <= started <= completed, "invalid run chronology")
        cohorts = run["cohorts"]
        maximum = 2 if run["workflow"] == WORKFLOWS[CORE] else 1
        _require(isinstance(cohorts, list) and 1 <= len(cohorts) <= maximum,
                 "invalid cohort inventory")
        previous = started
        for cohort in cohorts:
            _keys(cohort, "workers completed_at", "cohort")
            end = _time(cohort["completed_at"])
            _require(previous <= end <= completed, "invalid cohort chronology")
            previous = end
            workers = cohort["workers"]
            _require(isinstance(workers, list) and len(workers) == 12, "twelve allocation slots required")
            slots = []
            for worker in workers:
                _keys(worker, "slot runner_id outcome", "worker")
                _require(_integer(worker["slot"]) and worker["slot"] <= 12 and
                         isinstance(worker["outcome"], str) and
                         worker["outcome"] in {"pass", "environment", "failed", "incomplete"},
                         "invalid worker allocation")
                _require(_integer(worker["runner_id"], 0 if worker["outcome"] == "incomplete" else 1),
                         "actual runner identity required")
                _require(run["started_at"] is not None or worker["outcome"] == "incomplete",
                         "unstarted run cannot have completed allocations")
                slots.append(worker["slot"])
            _require(set(slots) == set(range(1, 13)), "duplicate or missing allocation slots")
    return index


def compact_index(registry, index, now):
    """Retire only superseded prefixes; retain recent live-reconciliation rows.

    A reviewed qualification inventory authorizes retirement of an older epoch.
    Missing anchors never authorize truncation of a currently enrolled epoch.
    Every current-epoch failure remains binding.
    """
    validate_registry(registry)
    validate_index(index)
    cutoff = now - LIVE_WINDOW
    by_id = {run["run_id"]: run for run in index["runs"]}
    epochs = {}
    for profile, workflow in WORKFLOWS.items():
        entry = registry["profiles"].get(profile)
        if entry is None:
            # No approved epoch exists. Old unapproved runs cannot satisfy
            # freshness; their individual immutable receipts remain available.
            epochs[workflow] = cutoff
            continue
        anchors = [by_id.get(identity) for identity in entry["qualification_runs"]]
        if all(anchor is not None and anchor["workflow"] == workflow for anchor in anchors):
            epochs[workflow] = min(_time(anchor["created_at"]) for anchor in anchors)
    return {"schema": 1, "runs": [
        run for run in index["runs"]
        if run["workflow"] not in epochs
        or _time(run["created_at"]) >= min(cutoff, epochs[run["workflow"]])
    ]}


def evaluate(registry, index, profile, installed_digest, now, observed_runs=None):
    """Return current approval; callers supply trusted, complete live run inventory.

    A new reviewed qualification inventory starts a new epoch. All later first
    attempts remain binding, including failures that leave the rolling window.
    Raw evidence hashes are checked by the publisher, not fetched repeatedly by
    each consumer. ``observed_runs`` is canonical GitHub workflow-run metadata.
    Cohort completion means every original worker job and validated packet is
    durably indexed. Later publisher/status-lookup outcomes do not add another
    measurement obligation; unavailable live authority still fails closed.
    """
    result = {"status": "suspended", "reasons": [], "latest_run": None, "expires_at": None}
    reasons = result["reasons"]
    try:
        validate_registry(registry)
        if profile not in registry["profiles"]:
            result.update(status="unapproved", reasons=["profile has no reviewed enrollment"])
            return result
        entry = registry["profiles"][profile]
        if installed_digest != entry["source_digest"]:
            result.update(status="unapproved", reasons=["installed implementation is not enrolled"])
            return result
        validate_index(index)
        if isinstance(now, str):
            now = _time(now)
        _require(isinstance(now, datetime) and now.tzinfo is not None and
                 now.utcoffset() == timedelta(0), "current UTC time required")
        by_id = {run["run_id"]: run for run in index["runs"]}
        qualification = entry["qualification_runs"]
        _require(all(identity in by_id for identity in qualification), "qualification evidence missing")
        epoch = min(_time(by_id[identity]["created_at"]) for identity in qualification)
        runs = sorted((run for run in index["runs"] if run["workflow"] == entry["workflow"]
                       and _time(run["created_at"]) >= epoch),
                      key=lambda run: (_time(run["created_at"]), run["run_id"]))
        _require([run["run_id"] for run in runs[:len(qualification)]] == qualification,
                 "qualification runs must be consecutive at the epoch start")
        expected = 2 if profile == CORE else 1
        _require(sum(len(by_id[identity]["cohorts"]) for identity in qualification) == expected,
                 "qualification cohort inventory is incomplete")
        for identity in qualification:
            _require(by_id[identity]["source_commit"] == entry["source_commit"],
                     "qualification must execute the exact enrolled source commit")

        if observed_runs is not None:
            _require(isinstance(observed_runs, list), "live run inventory must be a list")
            observed_ids = set()
            for observed in observed_runs:
                _require(isinstance(observed, dict), "invalid live run metadata")
                if (observed.get("path") != entry["workflow"] or observed.get("head_branch") != "main"
                        or observed.get("event") not in EVENTS):
                    continue
                created = _time(observed.get("created_at"))
                if created < epoch:
                    continue
                identity = observed.get("id")
                _require(_integer(identity) and identity not in observed_ids and created <= now
                         and _integer(observed.get("run_attempt"))
                         and _hex(observed.get("head_sha"), 40),
                         "duplicate or invalid live run identity")
                observed_ids.add(identity)
                if identity in by_id:
                    recorded = by_id[identity]
                    _require(recorded["workflow"] == entry["workflow"] and
                             _time(recorded["created_at"]) == created and recorded["event"] == observed["event"],
                             "live run identity contradicts retained evidence")
                    # Original worker outcomes already include execution and
                    # artifact-upload completion. A rerun or later publisher
                    # failure cannot replace or reinterpret those retained facts.
                    continue
                status = observed.get("status")
                _require(status in {"completed", "queued", "in_progress", "waiting", "pending", "requested"},
                         "unknown live execution status")
                if status == "completed" or observed["run_attempt"] > 1 or now - created > PENDING_ALLOWANCE:
                    reasons.append(f"run {identity} lacks complete first-attempt evidence")
            _require(all(run["run_id"] in observed_ids for run in runs
                         if _time(run["created_at"]) >= now - LIVE_WINDOW),
                     "recent retained runs missing from complete live inventory")

        workers_seen, window = set(), []
        previous = last_satisfactory = None
        for run in runs:
            identity = run["run_id"]
            _require(_time(run["completed_at"]) <= now, "future evidence cannot establish approval")
            identity_valid = (run["source_digest"] == entry["source_digest"] and
                              run["workflow_digest"] == entry["workflow_digest"])
            if not identity_valid:
                reasons.append(f"run {identity} changed the enrolled implementation or workflow")
            for cohort in run["cohorts"]:
                completed = _time(cohort["completed_at"])
                if previous is not None and (completed < previous or completed - previous > FRESHNESS):
                    reasons.append(f"run {identity} followed a stale or out-of-order cohort")
                previous = completed
                passed, valid = 0, identity_valid
                for worker in cohort["workers"]:
                    runner = worker["runner_id"]
                    if runner and runner in workers_seen:
                        reasons.append(f"run {identity} reused runner {runner}")
                        valid = False
                    if runner:
                        workers_seen.add(runner)
                    outcome = worker["outcome"]
                    if outcome == "pass":
                        passed += 1
                    elif outcome != "environment" or profile != CORE:
                        reasons.append(f"run {identity} slot {worker['slot']} is {outcome}")
                        valid = False
                window.append((passed, valid))
                window = window[-expected:]
                if len(window) == expected:
                    if sum(row[0] for row in window) < (23 if profile == CORE else 12):
                        reasons.append(f"run {identity} failed the profile availability requirement")
                    elif all(row[1] for row in window):
                        last_satisfactory = completed
            result["latest_run"] = identity
        if last_satisfactory is not None:
            expiry = last_satisfactory + FRESHNESS
            result["expires_at"] = _format(expiry)
            if now > expiry:
                reasons.append("latest satisfactory refresh is more than ten days old")
        else:
            reasons.append("no satisfactory qualification window")
        if not reasons:
            result["status"] = "active"
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        reasons.append(str(error))
    result["reasons"] = list(dict.fromkeys(reasons))
    return result
