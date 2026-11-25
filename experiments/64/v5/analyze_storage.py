"""Recompute v5 evidence without importing the candidate or mutable common code.

Frozen hashes below were independently fetched from the declared authority
commit. Original observations and provenance remain unchanged. All durations
stay raw; neither averaging nor selecting a minimum changes acceptance.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import statistics

SOURCE = "667318543d25ae4c8c85fe9f100622596ccbbe3d"
AUTHORITY = "6eb72376af796f132461be9deded28829adead67"
PRODUCT = "03de186a044c9c6b365347485a6c4093ce831c79"
EXPECTED_HASHES = {
    "timer": "bdd32412d84eca5c3a156edfba9bf4e60733f068ebba6d47bd5cfda5a8bc883f",
    "storage_cases": "c68b9ba664ee39e62337c40066417cf388cdab4b533b93f6c6a02f09d42fe94a",
    "central": "1f445c8ca8bebd480376611fb52d4691987b06ad88149d2aa191185c4086aa34",
    "product_adapter": "11ddf9d3ab5dffedf981f3fc2fecab1329a9d432051f595c6bd6f5ea9a0b164c",
    "plan": "c78c3b17121fbc00f2e13587dcddac8dc47c7d51b055ddd88b1056b5c7e65832",
    "product": "967e0c485c3ea2f50c82cc16f3971ca1c276182eda929299cf53e37b20cffc8a",
}
FIXTURE_SHA256 = "e2b3a325c2656969cc88573c78f625d0ae1d08578227fef4c6092de71123bf5a"
CORE_LIMITS = {"policy16_p1": 20_000_000, "policy16_p2": 30_000_000, "policy16_p4": 30_000_000,
               "policy512_p1": 500_000_000, "policy512_p2": 350_000_000, "policy512_p4": 300_000_000,
               "cycle48": 50_000_000, "cold16": 125_000_000, "copy16": 20_000_000}
STORAGE_LIMITS = {"copy16_sync": 100_000_000, "atomic16_p1": 100_000_000,
                  "atomic16_p2": 100_000_000, "atomic16_p4": 100_000_000,
                  "append64_sync": 150_000_000, "sqlite64_delete_full": 150_000_000,
                  "sqlite64_delete_extra": 150_000_000, "sqlite64_wal_full": 150_000_000,
                  "sqlite64_delete_extra_batch": 150_000_000, "sqlite64_wal_full_batch": 150_000_000}
PROBE_CAPS = {"cpu_serial": 350_000_000, "cpu_p4": 300_000_000, "sha256": 250_000_000,
              "warm_files": 150_000_000, "fdatasync64": 250_000_000}
PATHS = ("runner_temp", "memory", "distinct_mnt")
CONTROLS = ("atomic16_p1/wait", "sqlite64_wal_full/periodic_wait")
VERDICTS = ("pass", "mixed_miss", "all_over", "unqualified", "unavailable", "invalid_evidence")
GROUPS = {"ubuntu24": range(1, 13), "ubuntu22": range(13, 25), "overall": range(1, 25)}


def valid_duration(value):
    return type(value) is int and value > 0


def stats(values):
    values = [v for v in values if valid_duration(v)]
    return {"count": len(values), "minimum": min(values) / 1e6,
            "median": statistics.median(values) / 1e6, "maximum": max(values) / 1e6} if values else {"count": 0}


def raw_decision(samples, budget, admitted):
    if (not isinstance(samples, list) or len(samples) != 3 or
            any(not isinstance(s, dict) or s.get("verified") is not True or
                s.get("error") is not None or not valid_duration(s.get("wall_ns")) for s in samples)):
        return "invalid_evidence"
    if not admitted:
        return "unqualified"
    misses = sum(s["wall_ns"] > budget for s in samples)
    return "pass" if misses == 0 else "all_over" if misses == 3 else "mixed_miss"


def evaluate_profile(record):
    """Independent transcription of the frozen v4 generic admission contract."""
    core, sync = [], []
    if record.get("profile") != "public-linux-x64-4cpu-generic/v1":
        core.append("unknown profile")
    for when in ("metadata", "metadata_after"):
        m = record.get(when, {})
        checks = [
            (m.get("system") == "Linux", "Linux required"),
            (str(m.get("machine", "")).lower() in ("x86_64", "amd64"), "x64 required"),
            (m.get("logical_cpus") == 4, "four logical CPUs required"),
            (m.get("affinity_count") == 4, "affinity to four CPUs required"),
            (isinstance(m.get("memory_total_bytes"), int) and m["memory_total_bytes"] >= 14 * 1024**3, "MemTotal below 14 GiB"),
            (isinstance(m.get("free_bytes"), int) and m["free_bytes"] >= 512 * 1024**2, "free storage below 512 MiB"),
            (m.get("filesystem") not in (None, "tmpfs", "ramfs"), "memory filesystem or unknown filesystem"),
        ]
        core.extend(f"{when}: {reason}" for ok, reason in checks if not ok)
    for name, cap in PROBE_CAPS.items():
        reasons = sync if name == "fdatasync64" else core
        values = record.get("samples_ns", {}).get(name, [])
        if len(values) != 3 or any(not valid_duration(v) for v in values):
            reasons.append(f"{name}: missing or invalid observations")
        if record.get("errors", {}).get(name):
            reasons.append(f"{name}: execution or verification failure")
        if any(type(v) is int and v > cap for v in values):
            reasons.append(f"{name}: at least one observation exceeds {cap / 1e6:g} ms")
    return {"core_admitted": not core, "sync_admitted": not core and not sync,
            "core_reasons": core, "sync_reasons": core + sync}


def storage_admission(topology, core_admitted, name):
    reasons = [] if core_admitted else ["core profile not admitted"]
    filesystem = topology.get("filesystem")
    if name == "memory":
        if filesystem != "tmpfs":
            reasons.append("actual tmpfs required")
    elif not filesystem or filesystem in ("tmpfs", "ramfs", "overlay"):
        reasons.append("observed non-memory native filesystem required")
    return {"admitted": not reasons, "reasons": reasons,
            "claim": "volatile software path" if name == "memory" else "native filesystem API timing",
            "physical_persistence_qualified": False,
            "durability_cautions": topology.get("durability_cautions", [])}


def path_availability(record, name):
    checks, inventory = record.get("path_checks", {}), record.get("path_inventory", {})
    native = checks.get("runner_temp", {})
    if name == "runner_temp":
        facts = native
        expected = facts.get("exists") and facts.get("directory") and facts.get("writable")
        reason = "RUNNER_TEMP directory and write access"
    elif name == "memory":
        facts = checks.get("shm", {})
        expected = (facts.get("directory") and facts.get("writable") and
                    isinstance(facts.get("free_bytes"), int) and facts["free_bytes"] >= 64 * 1024**2 and
                    inventory.get("shm", {}).get("filesystem") == "tmpfs")
        reason = "actual writable tmpfs with at least 64 MiB free"
    else:
        facts = checks.get("mnt", {})
        expected = (facts.get("directory") and facts.get("writable") and
                    type(facts.get("device_number")) is int and type(native.get("device_number")) is int and
                    facts["device_number"] != native["device_number"])
        reason = "writable /mnt on a distinct device from RUNNER_TEMP"
    available = name in record.get("storage", {})
    unavailable = record.get("unavailable_paths", {}).get(name)
    prepare_error = isinstance(unavailable, dict) and str(unavailable.get("stage", "")).startswith("storage_prepare:")
    consistent = ((bool(expected) and available and unavailable is None) or
                  (not expected and not available and unavailable is not None) or
                  (bool(expected) and not available and prepare_error))
    return {"expected_from_path_facts": bool(expected), "available": available,
            "facts": facts, "requirement": reason, "reported_unavailable": unavailable,
            "preparation_error": prepare_error, "consistent": consistent}


def topology_consistent(topology):
    entries = topology.get("mount", {}).get("data", {}).get("filesystems", [])
    if not entries:
        return topology.get("filesystem") is None
    return (topology.get("filesystem") == entries[0].get("fstype") and
            topology.get("mount_options") == entries[0].get("options", "").split(",") and
            topology.get("physical_power_loss_survival_proven") is False)


def observation_detail(samples, budget, admitted, valid, case, stored=None):
    samples = samples if isinstance(samples, list) else []
    raw = raw_decision(samples, budget, admitted)
    errors = [s.get("error") for s in samples if isinstance(s, dict) and s.get("error") is not None]
    values = [s.get("wall_ns") for s in samples if isinstance(s, dict)]
    injected = [s.get("injected_wait_ns") for s in samples if isinstance(s, dict)]
    expected_wait = [0, 0, 0]
    if case.endswith("/wait"):
        expected_wait = [budget + 16_000_000] * 3
    elif case.endswith("/periodic_wait"):
        expected_wait[1] = budget + 16_000_000
    injection_valid = injected == expected_wait
    control = case in CONTROLS
    control_proven = (control and admitted and valid and injection_valid and
                      raw in ("mixed_miss", "all_over") and
                      all(valid_duration(v) and v > budget for v, wait in zip(values, expected_wait) if wait))
    return {"budget_ns": budget, "admitted": admitted, "raw_decision": raw,
            "decision": raw if valid and injection_valid else "invalid_evidence",
            "stored_decision": stored, "stored_decision_matches": stored == raw,
            "sample_count": len(samples), "raw_ns": values, "raw_ms": stats(values),
            "errors": errors, "injected_wait_ns": injected, "injection_matches_plan": injection_valid,
            "minimum_would_hide_miss": raw == "mixed_miss" and min(values) <= budget,
            "control_rejection_proven": control_proven if control else None,
            "receipts": [s.get("receipt") for s in samples if isinstance(s, dict) and "receipt" in s]}


def summarize(cells, ids, controls=None, integrity=True):
    selected = {i: cells.get(i, {"decision": "invalid_evidence", "admitted": False, "raw_ns": []}) for i in ids}
    counts = {v: sum(c["decision"] == v for c in selected.values()) for v in VERDICTS}
    admitted = [i for i, c in selected.items() if c.get("admitted")]
    normal_ok = bool(admitted) and all(selected[i]["decision"] == "pass" for i in admitted)
    controls_ok = True if controls is None else all(
        controls.get(i, {}).get(case, {}).get("control_rejection_proven") is True
        for i in admitted for case in CONTROLS)
    threshold = 23 if len(ids) == 24 else 11
    return {"expected_allocations": len(ids), "admitted_count": len(admitted), "admitted_ids": admitted,
            "counts": counts, "verdict_ids": {v: [i for i, c in selected.items() if c["decision"] == v] for v in VERDICTS},
            "all_raw_ms": stats([v for c in selected.values() for v in c.get("raw_ns", [])]),
            "admitted_raw_ms": stats([v for i in admitted for v in selected[i].get("raw_ns", [])]),
            "minimum_would_hide_miss_ids": [i for i, c in selected.items() if c.get("minimum_would_hide_miss")],
            "admission_coverage_met": len(admitted) >= threshold,
            "every_admitted_normal_passes": normal_ok, "controls_proven": controls_ok,
            "evidence_integrity": integrity,
            "usefulness_screen": integrity and len(admitted) >= threshold and normal_ok and controls_ok}


def analyze(directory):
    issues, input_files, envelopes, records = [], {}, {}, []
    def note(scope, message):
        issues.append({"scope": scope, "message": message})
    def load(filename):
        path = directory / filename
        try:
            data = path.read_bytes()
            input_files[filename] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            return json.loads(data)
        except (OSError, ValueError) as exc:
            note(filename, f"{type(exc).__name__}: {exc}")
            return {}
    provenance = load("provenance.json")
    expected_run = str(provenance.get("run_id"))
    for group in ("ubuntu24", "ubuntu22"):
        envelope = load(f"observations_{group}.json")
        envelopes[group] = {k: v for k, v in envelope.items() if k != "records"}
        for key, expected in (("source", SOURCE), ("authority_revision", AUTHORITY), ("run_attempt", "1"), ("run_id", expected_run)):
            if str(envelope.get(key)) != str(expected):
                note(group, f"envelope {key} mismatch: {envelope.get(key)!r}")
        group_records = envelope.get("records", [])
        if len(group_records) != 12:
            note(group, f"expected 12 records; found {len(group_records)}")
        for record in group_records:
            record = dict(record)
            record["_envelope_group"] = group
            records.append(record)
            if record.get("allocation") not in GROUPS[group]:
                note(group, f"unexpected allocation {record.get('allocation')!r}")
    for key, expected in (("source", SOURCE), ("authority_revision", AUTHORITY), ("run_attempt", "1")):
        if str(provenance.get(key)) != str(expected):
            note("provenance", f"{key} mismatch")
    if not expected_run.isdigit():
        note("provenance", "positive numeric workflow run ID required")
    prelaunch = provenance.get("prelaunch_failure", {})
    if (str(prelaunch.get("run_id")) != "45699461025" or prelaunch.get("worker_jobs") != 0 or
            prelaunch.get("source") != "9460ee3cb5ed1cf1d922c46ba5aa0dfbf990a7b3"):
        note("provenance", "zero-worker YAML prelaunch failure is missing or inconsistent")
    by_id = defaultdict(list)
    for record in records:
        by_id[record.get("allocation")].append(record)
    for allocation in range(1, 25):
        if len(by_id[allocation]) != 1:
            note(allocation, f"expected one record; found {len(by_id[allocation])}")
    for field in ("job_id", "runner_id"):
        values = [r.get(field) for r in records]
        if len(values) != 24 or any(type(v) is not int or v <= 0 for v in values) or len(set(values)) != 24:
            note("campaign", f"24 distinct positive {field} values not established")
    jobs = {j.get("id"): j for j in provenance.get("jobs", [])}
    artifacts = {a.get("name"): a for a in provenance.get("artifacts", [])}
    analyzed, all_core, all_storage = {}, {op: {} for op in CORE_LIMITS}, {p: {op: {} for op in STORAGE_LIMITS} for p in PATHS}
    controls = {p: {} for p in PATHS}
    record_errors, collection_errors = [], []
    for index, record in enumerate(records):
        allocation = record.get("allocation")
        errors = []
        def check(ok, message):
            if not ok:
                errors.append(message)
        check(record.get("format") == "all-storage-profile-experiment/v5", "observation format")
        for key, expected in (("source", SOURCE), ("authority_revision", AUTHORITY), ("product_base", PRODUCT),
                              ("python", "3.11.9"), ("fixture_sha256", FIXTURE_SHA256)):
            check(record.get(key) == expected, key + " mismatch")
        check(record.get("smoke") is False, "smoke observation")
        check(str(record.get("run_id")) == expected_run and str(record.get("run_attempt")) == "1", "run identity mismatch")
        check(record.get("hashes") == EXPECTED_HASHES, "frozen source hashes mismatch")
        check(record.get("core_limits_ns") == CORE_LIMITS and record.get("storage_limits_ns") == STORAGE_LIMITS, "fixed budgets mismatch")
        check(record.get("memory_required_free_bytes") == 64 * 1024**2, "memory free-space threshold mismatch")
        group = "ubuntu24" if type(allocation) is int and 1 <= allocation <= 12 else "ubuntu22"
        label = "ubuntu-24.04" if group == "ubuntu24" else "ubuntu-22.04"
        check(record.get("runner_label") == label, "runner label mismatch")
        check(record.get("complete") is True, "incomplete collection")
        check(record.get("collection_errors") == [], "collection error(s)")
        collection_errors.extend({"allocation": allocation, **e} for e in record.get("collection_errors", []))
        check(len(by_id[allocation]) == 1, "duplicate allocation")
        job = jobs.get(record.get("job_id"), {})
        check(bool(job) and job.get("runner_id") == record.get("runner_id"), "job/runner provenance mismatch")
        if job:
            check(str(job.get("run_id")) == expected_run, "job run mismatch")
            check(job.get("head_sha", SOURCE) == SOURCE, "job source mismatch")
        artifact = artifacts.get(f"storage-v5-{allocation}", {})
        check(bool(artifact), "artifact metadata missing")
        if artifact:
            workflow = artifact.get("workflow_run", {})
            check(str(workflow.get("id")) == expected_run and workflow.get("head_sha") == SOURCE, "artifact run/source mismatch")
        pre = evaluate_profile(record.get("preflight", {}))
        post = evaluate_profile(record.get("postflight", {}))
        check(pre == record.get("core_admission"), "preflight admission mismatch")
        check(post == record.get("postflight_core_admission"), "postflight diagnostic mismatch")
        check(record.get("postflight_used_for_acceptance") is False, "postflight acceptance mutation")
        check(set(record.get("core_samples", {})) == set(CORE_LIMITS), "core operation set mismatch")
        check(set(record.get("storage", {})) <= set(PATHS), "unexpected storage path")
        expected_cases = [op + "/normal" for op in STORAGE_LIMITS] + list(CONTROLS)
        for name, storage in record.get("storage", {}).items():
            check(set(storage.get("samples", {})) == set(expected_cases), "storage operation set mismatch: " + name)
            check(topology_consistent(storage.get("topology", {})), "inconsistent mount evidence: " + name)
        for name, facts in record.get("path_checks", {}).items():
            topology = record.get("path_inventory", {}).get(name, {})
            if facts.get("exists"):
                check(topology_consistent(topology), "inconsistent inventory mount evidence: " + name)
                dev = facts.get("device_number")
                if type(dev) is int:
                    check(topology.get("device") == f"{os.major(dev)}:{os.minor(dev)}", "inventory device mismatch: " + name)
        ordered_cases = [(name, case) for name in PATHS if name in record.get("storage", {}) for case in expected_cases]
        ordered_cases += [("core", op) for op in CORE_LIMITS]
        expected_order = []
        if type(allocation) is int:
            for repeat in range(3):
                offset = (allocation + repeat - 1) % len(ordered_cases)
                order = ordered_cases[offset:] + ordered_cases[:offset]
                if (allocation + repeat) % 2 == 0:
                    order.reverse()
                expected_order.extend([repeat, location, case] for location, case in order)
        check(record.get("execution_order") == expected_order, "operation execution order or extent mismatch")
        for when in ("preflight", "postflight"):
            for metadata in ("metadata", "metadata_after"):
                m = record.get(when, {}).get(metadata, {})
                check(m.get("source_sha256") == EXPECTED_HASHES["central"], when + " probe source mismatch")
                check(m.get("python") == "3.11.9", when + " runtime mismatch")
                check(m.get("image_os") == group, when + " OS group mismatch")
        source_valid = not errors
        core_admitted = pre["core_admitted"] and source_valid
        result = {"allocation": allocation, "group": group, "source_valid": source_valid,
                  "job_id": record.get("job_id"), "runner_id": record.get("runner_id"),
                  "errors": errors, "complete": record.get("complete"), "collection_errors": record.get("collection_errors", []),
                  "preflight_admission": pre, "postflight_admission": post, "path_availability": {}, "storage": {}, "core": {},
                  "harness_ns": record.get("finished_unix_ns", 0) - record.get("started_unix_ns", 0),
                  "metadata": record.get("preflight", {}).get("metadata", {})}
        for op, budget in CORE_LIMITS.items():
            cell = observation_detail(record.get("core_samples", {}).get(op, []), budget, pre["core_admitted"], source_valid,
                                      op, record.get("core_decisions", {}).get(op))
            cell["admitted"] = core_admitted
            result["core"][op] = cell
            all_core[op][allocation] = cell
            check(cell["stored_decision_matches"], f"stored core verdict mismatch: {op}")
        for name in PATHS:
            availability = path_availability(record, name)
            result["path_availability"][name] = availability
            check(availability["consistent"], f"path availability mismatch: {name}")
            if not availability["available"]:
                verdict = "unavailable" if availability["consistent"] and not availability["preparation_error"] else "invalid_evidence"
                for op in STORAGE_LIMITS:
                    all_storage[name][op][allocation] = {"decision": verdict, "admitted": False, "raw_ns": [], "raw_decision": verdict}
                continue
            storage = record["storage"][name]
            admission = storage_admission(storage.get("topology", {}), pre["core_admitted"], name)
            check(admission == storage.get("admission"), f"stored storage admission mismatch: {name}")
            result["storage"][name] = {"admission": admission, "topology": storage.get("topology"),
                                       "topology_after": storage.get("topology_after"), "cases": {}}
            controls[name][allocation] = {}
            for case in [op + "/normal" for op in STORAGE_LIMITS] + list(CONTROLS):
                budget = STORAGE_LIMITS[case.split("/")[0]]
                cell = observation_detail(storage.get("samples", {}).get(case, []), budget, admission["admitted"],
                                          source_valid and availability["consistent"], case, storage.get("decisions", {}).get(case))
                cell["admitted"] = admission["admitted"] and source_valid and availability["consistent"]
                result["storage"][name]["cases"][case] = cell
                check(cell["stored_decision_matches"], f"stored storage verdict mismatch: {name}/{case}")
                check(cell["injection_matches_plan"], f"injected wait mismatch: {name}/{case}")
                if case in CONTROLS:
                    controls[name][allocation][case] = cell
                else:
                    all_storage[name][case.split("/")[0]][allocation] = cell
        if errors:
            record_errors.append({"allocation": allocation, "errors": errors})
        analyzed[str(allocation) if len(by_id[allocation]) == 1 else f"{allocation}:record-{index}"] = result
    integrity = not issues and not record_errors and len(records) == 24
    summary_core, summary_storage = {}, {}
    for op, cells in all_core.items():
        groups = {name: summarize(cells, list(ids), integrity=integrity) for name, ids in GROUPS.items()}
        groups["overall"]["usefulness_screen"] &= all(groups[g]["usefulness_screen"] for g in ("ubuntu24", "ubuntu22"))
        summary_core[op] = {"budget_ns": CORE_LIMITS[op], "groups": groups}
    for path in PATHS:
        summary_storage[path] = {}
        for op, cells in all_storage[path].items():
            groups = {name: summarize(cells, list(ids), controls[path], integrity) for name, ids in GROUPS.items()}
            groups["overall"]["usefulness_screen"] &= all(groups[g]["usefulness_screen"] for g in ("ubuntu24", "ubuntu22"))
            summary_storage[path][op] = {"budget_ns": STORAGE_LIMITS[op], "groups": groups}
    probe_summary = {}
    for when in ("preflight", "postflight"):
        probe_summary[when] = {name: {"cap_ns": cap,
            "raw_ms": stats([v for r in records for v in r.get(when, {}).get("samples_ns", {}).get(name, [])]),
            "over_cap_ids": [r.get("allocation") for r in records if any(type(v) is int and v > cap for v in r.get(when, {}).get("samples_ns", {}).get(name, []))],
            "errors": [{"allocation": r.get("allocation"), "errors": r[when]["errors"][name]} for r in records if r.get(when, {}).get("errors", {}).get(name)]}
            for name, cap in PROBE_CAPS.items()}
    resources = {field: dict(Counter(str(r.get("preflight", {}).get("metadata", {}).get(field)) for r in records))
                 for field in ("cpu_model", "image_os", "image_version", "kernel", "python", "filesystem")}
    timing_counts = {
        "core": sum(len(v) for r in records for v in r.get("core_samples", {}).values()),
        "storage": sum(len(v) for r in records for p in r.get("storage", {}).values() for v in p.get("samples", {}).values()),
        "generic_probes": sum(len(v) for r in records for phase in ("preflight", "postflight") for v in r.get(phase, {}).get("samples_ns", {}).values()),
    }
    timing_counts["total"] = sum(timing_counts.values())
    timing_counts["expected_from_available_paths"] = 24 * (9 * 3 + 2 * 5 * 3) + 12 * 3 * sum(len(r.get("storage", {})) for r in records)
    topology_summary = {}
    def devices(items):
        for item in items:
            yield item
            yield from devices(item.get("children", []))
    for path in PATHS:
        topologies = [r["storage"][path]["topology"] for r in records if path in r.get("storage", {})]
        models = Counter()
        for topology in topologies:
            models.update({b["model"] for b in devices(topology.get("block_devices", {}).get("data", {}).get("blockdevices", [])) if b.get("model")})
        topology_summary[path] = {
            "available_count": len(topologies),
            "actual_filesystems": dict(Counter(str(t.get("filesystem")) for t in topologies)),
            "mount_option_sets": dict(Counter(",".join(t.get("mount_options", [])) for t in topologies)),
            "mount_sources": dict(Counter(str(t.get("mount", {}).get("data", {}).get("filesystems", [{}])[0].get("source")) for t in topologies)),
            "sqlite_versions": dict(Counter(str(t.get("sqlite_version")) for t in topologies)),
            "block_models_visible_on_workers": dict(models),
        }
    native_misses = [c for cells in all_storage["runner_temp"].values() for c in cells.values() if c["decision"] in ("mixed_miss", "all_over")]
    native_miss_summary = {"worker_case_groups": len(native_misses),
                          "mixed_groups": sum(c["decision"] == "mixed_miss" for c in native_misses),
                          "all_over_groups": sum(c["decision"] == "all_over" for c in native_misses),
                          "over_budget_observations": sum(sum(v > c["budget_ns"] for v in c["raw_ns"]) for c in native_misses),
                          "minimum_would_hide_groups": sum(c["minimum_would_hide_miss"] for c in native_misses),
                          "allocation_ids": sorted({i for cells in all_storage["runner_temp"].values() for i, c in cells.items() if c["decision"] in ("mixed_miss", "all_over")})}
    return {"format": "all-storage-profile-analysis/v5", "source": SOURCE, "authority_revision": AUTHORITY,
            "product_base": PRODUCT, "run_id": provenance.get("run_id"), "run_attempt": 1,
            "expected_hashes": EXPECTED_HASHES, "expected_fixture_sha256": FIXTURE_SHA256,
            "inputs": input_files, "envelopes": envelopes, "provenance": provenance,
            "artifact_zip_bytes_verified": False,
            "source_hash_validation_passed": len(records) == 24 and all(r.get("hashes") == EXPECTED_HASHES and
                 r.get("source") == SOURCE and r.get("authority_revision") == AUTHORITY for r in records),
            "evidence_integrity_passed": integrity, "validation_issues": issues, "record_validation_errors": record_errors,
            "collection_errors": collection_errors, "record_count": len(records),
            "unique_job_ids": len(set(r.get("job_id") for r in records)),
            "unique_runner_ids": len(set(r.get("runner_id") for r in records)),
            "core": summary_core, "storage": summary_storage, "records": analyzed,
            "probes": probe_summary, "resources": resources,
            "timing_counts": timing_counts, "topology_summary": topology_summary,
            "native_normal_misses": native_miss_summary,
            "harness_raw_ms": stats([v["harness_ns"] for v in analyzed.values()]),
            "physical_persistence_qualified": False,
            "interpretation": "Raw API timing only; no physical power-loss or guaranteed durable-completion qualification."}


def render(analysis):
    a = analysis
    lines = ["# V5 storage profile results", "", a["interpretation"], "",
             f"Source: `{SOURCE}`. Authority: `{AUTHORITY}`.", "",
             f"Run: https://github.com/nashspence/all/actions/runs/{a['run_id']}", "",
             f"Records retained: **{a['record_count']}/24**. Distinct jobs: **{a['unique_job_ids']}**. "
             f"Distinct runners: **{a['unique_runner_ids']}**. Evidence integrity: **{'pass' if a['evidence_integrity_passed'] else 'FAIL'}**.", "",
             f"Exact duration count: **{a['timing_counts']['total']:,}** = {a['timing_counts']['core']:,} core + "
             f"{a['timing_counts']['storage']:,} storage + {a['timing_counts']['generic_probes']:,} generic-probe observations. "
             f"The declared available-path extent requires {a['timing_counts']['expected_from_available_paths']:,}.", "",
             "The initial workflow source failed YAML validation before any worker allocation. Its zero-worker failure is retained in provenance. "
             "The corrected workflow uses the same frozen authority. Original first-attempt log integers are analyzed; artifact metadata is checked, but ZIP bytes were not downloaded or independently authenticated.", "",
             "## Acceptance rule", "", "A valid admitted observation group passes only when all three raw durations are at or below its fixed budget. "
             "A campaign usefulness pass additionally requires at least 23/24 admitted allocations, at least 11/12 in each OS group, "
             "every admitted normal observation passing, and valid measured rejection of both applicable storage delay controls. "
             "The minimum is diagnostic only. Postflight cannot erase a miss.", ""]
    def table(title, mapping):
        lines.extend(["## " + title, "", "| Operation | B ms | Admitted | Pass | Mixed | All over | Unqualified | Unavailable | Invalid | Raw admitted max ms | Screen |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"])
        for op, value in mapping.items():
            s = value["groups"]["overall"]
            c = s["counts"]
            maximum = s["admitted_raw_ms"].get("maximum")
            maximum = "—" if maximum is None else f"{maximum:.3f}"
            lines.append(f"| {op} | {value['budget_ns']/1e6:g} | {s['admitted_count']}/24 | {c['pass']} | {c['mixed_miss']} | {c['all_over']} | {c['unqualified']} | {c['unavailable']} | {c['invalid_evidence']} | {maximum} | {'pass' if s['usefulness_screen'] else 'fail'} |")
        lines.append("")
    table("Core operations", a["core"])
    for path, mapping in a["storage"].items():
        table(f"Storage path: {path}", mapping)
    lines.extend(["## Per-OS results", "", "Each cell shows admitted / passing allocations out of 12, followed by the OS-group screen.", "",
                  "| Path | Operation | Ubuntu 24.04 | Ubuntu 22.04 |", "|---|---|---|---|"])
    for path, mapping in [("core", a["core"]), *a["storage"].items()]:
        for op, value in mapping.items():
            cells = []
            for group in ("ubuntu24", "ubuntu22"):
                s = value["groups"][group]
                cells.append(f"{s['admitted_count']} / {s['counts']['pass']} ({'pass' if s['usefulness_screen'] else 'fail'})")
            lines.append(f"| {path} | {op} | {' | '.join(cells)} |")
    lines.extend(["", "## Path availability and mount evidence", ""])
    for path in PATHS:
        available, unavailable, cautions, filesystems, devices = [], {}, Counter(), Counter(), Counter()
        for r in a["records"].values():
            p = r["path_availability"].get(path, {})
            if p.get("available"):
                available.append(r["allocation"])
                t = r["storage"][path]["topology"]
                filesystems[str(t.get("filesystem"))] += 1
                devices[str(t.get("device"))] += 1
                cautions.update(t.get("durability_cautions", []))
            else:
                unavailable[str(r["allocation"])] = p.get("reported_unavailable")
        lines.extend([f"### {path}", "", f"Available on {len(available)}/24 allocations. Filesystems: `{dict(filesystems)}`. "
                      f"Observed device-number distribution: `{dict(devices)}`.", "",
                      f"Durability cautions: `{dict(cautions)}`. These are observed configuration facts, not a power-loss test.", ""])
        lines.extend(["```json", json.dumps(a["topology_summary"][path], indent=2, sort_keys=True), "```", ""])
        if unavailable:
            lines.extend(["Unavailable allocations and recorded reasons:", "", "```json", json.dumps(unavailable, indent=2, sort_keys=True), "```", ""])
    lines.extend(["## Controls", "", "Only verified complete executions with the specified injected delay and an actually measured over-budget result count as proven rejection. Invalid executions are separate.", "",
                  "| Path | Control | Admitted | Proven rejects | Invalid executions |", "|---|---|---:|---:|---:|"])
    for path in PATHS:
        for case in CONTROLS:
            cells = [r["storage"][path]["cases"][case] for r in a["records"].values() if path in r["storage"]]
            lines.append(f"| {path} | {case} | {sum(c['admitted'] for c in cells)} | {sum(c['control_rejection_proven'] is True for c in cells)} | {sum(c['decision']=='invalid_evidence' for c in cells)} |")
    lines.extend(["", "## Every admitted normal miss", "", "```json", json.dumps(a["native_normal_misses"], indent=2, sort_keys=True), "```", "",
                  "| Allocation | Path | Operation | Raw observations ms | Verdict |", "|---:|---|---|---|---|"])
    misses = 0
    for r in a["records"].values():
        collections = [("core", r["core"])] + [(path, v["cases"]) for path, v in r["storage"].items()]
        for path, cells in collections:
            for case, c in cells.items():
                if case in CONTROLS or c["decision"] not in ("mixed_miss", "all_over"):
                    continue
                misses += 1
                lines.append(f"| {r['allocation']} | {path} | {case} | {', '.join(f'{v/1e6:.3f}' for v in c['raw_ns'])} | {c['decision']} |")
    if not misses:
        lines.append("| — | — | — | No admitted normal misses | — |")
    lines.extend(["", "## Generic probe evidence", "", "The sync probe remains diagnostic. It grants no physical persistence qualification.", "",
                  "| Phase | Probe | Cap ms | Raw min ms | Raw median ms | Raw max ms | Over-cap allocations |", "|---|---|---:|---:|---:|---:|---|"])
    for phase, probes in a["probes"].items():
        for name, p in probes.items():
            s = p["raw_ms"]
            values = [f"{s[k]:.3f}" if k in s else "—" for k in ("minimum", "median", "maximum")]
            lines.append(f"| {phase} | {name} | {p['cap_ns']/1e6:g} | {' | '.join(values)} | {p['over_cap_ids']} |")
    lines.extend(["", "## Resources and cost", "", "```json", json.dumps({"resources": a["resources"], "harness_ms": a["harness_raw_ms"]}, indent=2, sort_keys=True), "```", "",
                  "Harness cost includes preparation, verification and reset, generic probes, normal cases and deliberate waits. It is not the cost of a minimal CI gate.", "",
                  "## Evidence errors", "", "```json", json.dumps({"validation": a["validation_issues"], "record_validation": a["record_validation_errors"], "collection": a["collection_errors"]}, indent=2, sort_keys=True), "```", "",
                  "## Scope", "", "These fixed numbers demonstrate a raw timing protocol; they do not become Riverhog or Fishhat's design budgets. "
                  "The batch cases change acknowledgment granularity. The legacy cases retain their original namespace synchronization limitations. "
                  "Single-connection SQLite evidence does not qualify concurrent database use. A same-day finite campaign does not establish later-date reliability or a bound on rare latency tails. "
                  "Passing on tmpfs or relaxed native mounts cannot satisfy a stronger physical durability requirement.", "",
                  "The two OS groups also differ in SQLite library version, kernels and hardware; this campaign does not identify the OS itself as the cause of any difference. "
                  "Unavailable /mnt means no qualifying preexisting writable path there. Other block devices visible in lsblk were not reconfigured or qualified.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = analyze(args.directory)
    (args.directory / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (args.directory / "RESULTS.md").write_text(render(result))
    print(json.dumps({"record_count": result["record_count"], "evidence_integrity_passed": result["evidence_integrity_passed"],
                      "validation_issue_count": len(result["validation_issues"]), "record_error_count": len(result["record_validation_errors"])}))


if __name__ == "__main__":
    main()
