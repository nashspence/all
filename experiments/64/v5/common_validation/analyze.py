"""Finite analysis of the frozen twelve-worker installed-package campaign.

No live probes, product execution, refitting, time normalization or retries.
Source hashes were obtained from the immutable GitHub commits before analysis.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

HERE = Path(__file__).resolve().parent
SHARED = "a324c2a1c203ac2478afaac127f385f9e1e264d3"
AUTHORITY = "ed6c2dd701d5a8969166872af48b9d434d6f8af3"
ACTIVATION = "b0d7b03b8e3ffe16932d7036d1df111e088c7782"
RUN_ID = 45705830013
CAMPAIGN = "shared-package-v5-12"
OPERATIONS = ("check_repository16_warm", "check_repository16_cold")
EXPECTED_BUDGETS = dict(zip(OPERATIONS, (20_000_000, 125_000_000)))
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def positive(value):
    return type(value) is int and value > 0


def stats(values):
    values = [v for v in values if positive(v)]
    return ({"count": len(values), "min_ns": min(values), "max_ns": max(values),
             "median_ns": statistics.median(values), "sum_ns": sum(values)} if values
            else {"count": 0, "min_ns": None, "max_ns": None, "median_ns": None, "sum_ns": 0})


def frozen_package(shared_checkout):
    shared = Path(shared_checkout).resolve(strict=True)
    frozen = json.loads((HERE / "frozen_sources.json").read_text())
    assert (frozen["shared_revision"], frozen["authority_revision"], frozen["activation_revision"]) == (SHARED, AUTHORITY, ACTIVATION)
    for name, expected in frozen["files_sha256"].items():
        assert sha((shared / name).read_bytes()) == expected, "explicit shared checkout differs from frozen source: " + name
    assert sha((HERE / "PLAN.md").read_bytes()) == frozen["publication_sha256"]["plan"]
    workflow = (HERE / "performance-common-64.yml.template").read_text().replace("AUTHORITY_REVISION", AUTHORITY)
    assert sha(workflow.encode()) == frozen["publication_sha256"]["workflow"]
    # The evidence branch need not contain the implementation. Never import an
    # implicit implementation from that checkout or the installed environment.
    sys.path.insert(0, str(shared))
    from all_policy.performance import profiles, qualify_storage
    from all_policy.performance.contracts import Limit, evaluate
    for module in (profiles, qualify_storage, sys.modules[evaluate.__module__]):
        assert Path(module.__file__).resolve() == shared / "all_policy/performance" / Path(module.__file__).name, "shared module imported from a different checkout; use a fresh analysis process"
    limits = json.loads((shared / "examples/performance/limits.json").read_text())["operations"]
    bindings = json.loads((shared / "examples/performance/bindings.json").read_text())["operations"]
    assert {name: row["max_wall_ns"] for name, row in limits.items()} == EXPECTED_BUDGETS
    return frozen, profiles, qualify_storage, Limit, evaluate, limits, bindings


def analyze(document, provenance, shared_checkout):
    frozen, profiles, qualifier, Limit, evaluate, limits, bindings = frozen_package(shared_checkout)
    errors, workers, failures = [], [], []

    def check(condition, message, worker=None):
        if not condition:
            errors.append({"worker": worker, "error": message})

    def source(source, executable, worker):
        check(source.get("files_sha256") == frozen["module_files_sha256"], "installed module hashes", worker)
        check(source.get("package_sha256") == frozen["package_sha256"], "installed package digest", worker)
        check((source.get("package"), source.get("module"), source.get("version"), source.get("python"), source.get("executable"))
              == ("nashspence-all", "all_policy.performance", "0", "3.11.9", executable), "installed package/runtime identity", worker)

    rows = document.get("records", [])
    check(len(rows) == 12 and sorted(r.get("worker", -1) for r in rows) == list(range(1, 13)), "twelve unique worker records")
    run, jobs = provenance["run"], provenance["jobs"]
    artifacts = provenance["artifacts"]["artifacts"]
    mapping = provenance["collection"]["worker_jobs"]
    check((provenance["campaign"], provenance["source"], provenance["authority"], provenance["shared"])
          == (CAMPAIGN, ACTIVATION, AUTHORITY, SHARED), "collection provenance tuple")
    check((run["id"], run["head_sha"], run["run_attempt"], run["event"], run["head_branch"], run["path"])
          == (RUN_ID, ACTIVATION, 1, "push", "experiment/64-runner-calibration", ".github/workflows/performance-common-64.yml"), "first-attempt run identity")
    check(run["status"] == "completed", "run completed")
    check(len(jobs) == 12 and {j["name"] for j in jobs} == {f"common-{i}" for i in range(1, 13)}, "twelve matrix jobs")
    check(len({j["id"] for j in jobs}) == 12 and len({j["runner_id"] for j in jobs}) == 12, "distinct job/runner allocations")
    check(len(artifacts) == provenance["artifacts"]["total_count"] == 12, "twelve artifact metadata entries")
    check({a["name"] for a in artifacts} == {f"common-package-{i}" for i in range(1, 13)}, "artifact names")
    check(len(mapping) == 12 and {m["worker"] for m in mapping} == set(range(1, 13)), "complete worker/job mapping")
    for artifact in artifacts:
        check(positive(artifact["size_in_bytes"]) and artifact["expired"] is False
              and re.fullmatch(r"sha256:[0-9a-f]{64}", artifact["digest"]), "artifact metadata integrity")
        check((artifact["workflow_run"]["id"], artifact["workflow_run"]["head_sha"]) == (RUN_ID, ACTIVATION), "artifact run provenance")
    for record in sorted(rows, key=lambda r: r.get("worker", -1)):
        worker = record.get("worker")
        try:
            job = next(j for j in jobs if j["name"] == f"common-{worker}")
            mapped = next(m for m in mapping if m["worker"] == worker)
            check((mapped["job_id"], mapped["runner_id"]) == (job["id"], job["runner_id"]), "worker/job inventory join", worker)
            check((job["head_sha"], job["run_id"], job["run_attempt"], job["status"], job["labels"])
                  == (ACTIVATION, RUN_ID, 1, "completed", ["ubuntu-24.04"]), "job provenance and allocation label", worker)
            check(record["runner_name"] == job["runner_name"] and record["job_name"] == job["name"], "runner name join", worker)
            check((record["schema"], record["campaign"], record["repository"], int(record["run_id"]), record["run_attempt"])
                  == (1, CAMPAIGN, "nashspence/all", RUN_ID, 1), "record identity", worker)
            check((record["shared_revision"], record["subject_revision"], record["authority_revision"], record["workflow_sha"], record["activation_sha"])
                  == (SHARED, SHARED, AUTHORITY, ACTIVATION, ACTIVATION), "frozen revision tuple", worker)
            check(record["workflow_ref"] == "nashspence/all/.github/workflows/performance-common-64.yml@refs/heads/experiment/64-runner-calibration", "workflow ref", worker)
            check((record["python"], record["pyyaml"], record["runner_os"], record["runner_arch"], record["image_os"])
                  == ("3.11.9", "6.0.3", "Linux", "X64", "ubuntu24"), "runtime/image scope", worker)
            check(record["collection_error"] is None, "common collection error: " + str(record["collection_error"]), worker)
            command = record["command"]
            check(len(command) == 16 and command[:7] == [record["executable"], "-I", "-B", "-m", "all_policy", "performance", "--authority"], "actual installed command", worker)
            authority, subject = Path(command[7]), Path(command[13])
            root = command[15].split("=", 1)[1]
            check(command[8:13] == ["--approved-revision", AUTHORITY, "--repository", "nashspence/all", "--subject"]
                  and command[14:15] == ["--storage"] and command[15].startswith(profiles.CORE + "="), "authority/subject/storage arguments", worker)
            check(authority == subject.parent / "authority" and subject.name == "subject" and Path(root).name == "common-package-storage", "separate checkout/storage paths", worker)
            installed = Path(record["installed_module_path"])
            check(not any(installed.is_relative_to(subject.parent / name) for name in ("runtime", "subject", "authority")), "installed package outside source checkouts", worker)
            source(record["installed_source"], record["executable"], worker)
            expected_documents = {name: frozen["files_sha256"][f"examples/performance/{name}.json"] for name in ("limits", "bindings")}
            check(record["authority_documents_sha256"] == expected_documents, "approved document hashes", worker)
            check(record["adapter_sha256"] == frozen["files_sha256"]["examples/performance/all_policy_case.py"], "real operation and oracle source hash", worker)
            result = record["result"]
            check(sha((json.dumps(result, sort_keys=True) + "\n").encode()) == record["stdout_sha256"], "common raw JSON serialization digest", worker)
            check(record["stderr_sha256"] == EMPTY_SHA, "common stderr digest", worker)
            check((result["authority_revision"], result["candidate_revision"], result["limits_sha256"], result["bindings_sha256"])
                  == (AUTHORITY, SHARED, expected_documents["limits"], expected_documents["bindings"]), "gate authority/source provenance", worker)
            check(result.get("source_error") is None and result.get("error") is None, "gate source/execution error", worker)
            source(result["shared_source"], record["executable"], worker)
            check(result["shared_source"] == record["installed_source"], "collector/gate installed source identity", worker)
            check(set(result["preflights"]) == {root}, "one actual-root preflight", worker)
            preflight = result["preflights"][root]
            check(set(preflight["samples_ns"]) == set(profiles.CAPS_NS), "all five generic probes retained", worker)
            for name, values in preflight["samples_ns"].items():
                check(len(values) == 3 and all(positive(v) for v in values), f"three positive {name} observations", worker)
            check(preflight["errors"] == [], "generic probe execution errors", worker)
            admission = profiles.admit(profiles.CORE, preflight)
            meta = preflight["metadata"]
            check(meta["root"] == root and meta["image_version"] == record["image_version"] and meta["image_os"] == record["image_os"], "preflight environment linkage", worker)
            check(set(result["operations"]) == set(OPERATIONS), "both real operations present", worker)
            per_operation = {}
            for name in OPERATIONS:
                row = result["operations"][name]
                check(row["admission"] == admission, f"{name} recomputed admission", worker)
                observations = row["observations"]
                decision = evaluate(Limit(**limits[name]), admission, observations)
                if row["excluded_stages"].get("error"):
                    decision["verdict"] = "failed"
                check(row["decision"] == decision, f"{name} recomputed raw decision", worker)
                check(all(row[k] == bindings[name][k] for k in ("mode", "unit", "completion")), f"{name} approved semantic boundary", worker)
                for observation in observations:
                    check(positive(observation["elapsed_ns"]), f"{name} positive raw duration", worker)
                    check(positive(observation.get("verification_ns")), f"{name} verification measurement", worker)
                if row["mode"] == "request" and decision["verdict"] == "pass":
                    check(all(positive(row["excluded_stages"].get(k)) for k in ("startup_ns", "drain_ns")), "warm excluded costs retained", worker)
                elif row["mode"] == "command":
                    check(row["excluded_stages"] == {}, "cold complete-command boundary", worker)
                per_operation[name] = {"decision": decision, "observations": observations,
                                       "excluded_stages": row["excluded_stages"]}
                if decision["verdict"] != "pass":
                    failures.append({"worker": worker, "operation": name, "verdict": decision["verdict"],
                                     "miss_kind": decision.get("miss_kind")})
            gate_verdict = next(v for v in ("failed", "miss", "unqualified", "pass")
                                if v in {r["decision"]["verdict"] for r in per_operation.values()})
            check(result["verdict"] == gate_verdict and record["cli_exit_code"] == {"pass": 0, "miss": 1, "unqualified": 2, "failed": 3}[gate_verdict], "recomputed cohort verdict and exit", worker)
            native = record["native_qualification"]
            packet, summary = native["packet"], native["summary"]
            native_command = [record["executable"], "-I", "-B", "-m", "all_policy.performance.qualify_storage", "--root", root,
                              "--output", str(subject.parent / "common-output/storage-qualification.json")]
            check(native["command"] == native_command and native["not_run"] is False, "installed native collector invocation", worker)
            check(native["collection_error"] is None and native["outer_timed_out"] is False
                  and native["outer_watchdog_seconds"] == 60 and native["package_deadline_seconds"] == 300, "native collection/deadline evidence", worker)
            check(sha((json.dumps(packet, sort_keys=True, indent=2) + "\n").encode()) == native["packet_sha256"], "native checkpoint serialization digest", worker)
            native_stdout = {"status": summary["status"], "profile_approved": summary["profile_approved"], "evidence": summary["evidence"]}
            check(sha((json.dumps(native_stdout) + "\n").encode()) == native["stdout_sha256"] and native["stderr_sha256"] == EMPTY_SHA, "native stdout/stderr serialization digests", worker)
            check(packet["schema"] == qualifier.SCHEMA and packet["root"] == root and packet["resolved_root"] == root and packet["python"] == "3.11.9", "native packet identity", worker)
            check(packet["shared_source_sha256"] == frozen["module_files_sha256"], "native collector source hashes", worker)
            check(packet["fixed_probe_caps_ns"] == qualifier.CAPS_NS and packet["repetitions"] == 3, "native witness constants unchanged", worker)
            topology = packet["topology"]
            reasons = qualifier.configuration_reasons(topology)
            check(reasons == packet["configuration_reasons"], "recomputed native configuration rejection", worker)
            check(topology["path"] == root and topology["filesystem"] == meta["mount"]["fstype"]
                  and topology["device"] == meta["mount"]["maj:min"]
                  and set(topology["mount_options"]) == set(meta["mount"]["options"].split(",")), "same actual storage scope", worker)
            check(packet["profile_approved"] is False and packet["physical_persistence_proven"] is False
                  and topology["physical_power_loss_survival_proven"] is False and summary["profile_approved"] is False, "no physical/profile approval claim", worker)
            check(summary["status"] == packet["status"] and summary["evidence"] == native_command[-1], "native summary/packet linkage", worker)
            coordinator = packet["coordinator"]
            rejected = bool(reasons) and packet["status"] == "environment_unqualified" and native["cli_exit_code"] == 2
            complete_rejection = (rejected and packet["errors"] == [] and packet["operations"] == {}
                                  and coordinator["complete"] is True and coordinator["timed_out"] is False
                                  and coordinator["worker_returncode"] == 0 and coordinator["deadline_seconds"] == 300
                                  and not coordinator.get("termination_unconfirmed") and native["collection_error"] is None)
            if reasons and not complete_rejection:
                failures.append({"worker": worker, "operation": "native_rejection_control", "verdict": packet["status"]})
            check(coordinator["snapshots_received"] >= 3, "incremental native packet snapshots", worker)
            for key, value in (("common_cli", record["cli_wall_ns"]), ("gate_total", result["total_ns"]),
                               ("preflight", preflight["total_ns"]), ("native_cli", native["cli_wall_ns"]),
                               ("native_coordinator", coordinator["elapsed_ns"]), ("native_collect", packet["total_ns"])):
                check(positive(value), f"positive {key} cost", worker)
            workers.append({"worker": worker, "job_id": job["id"], "runner_id": job["runner_id"],
                            "cpu_model": meta["cpu_model"], "image_version": meta["image_version"],
                            "mount_source": meta["mount"]["source"], "mount_options": topology["mount_options"],
                            "sqlite_version": topology["sqlite_version"], "core_admission": admission,
                            "probe_samples_ns": preflight["samples_ns"], "operations": per_operation,
                            "cli_wall_ns": record["cli_wall_ns"], "gate_total_ns": result["total_ns"],
                            "preflight_ns": preflight["total_ns"], "native_cli_ns": native["cli_wall_ns"],
                            "native_coordinator_ns": coordinator["elapsed_ns"], "native_collect_ns": packet["total_ns"],
                            "native_status": packet["status"], "native_configuration_reasons": reasons,
                            "native_rejection_applicable": bool(reasons), "native_rejection_complete": complete_rejection,
                            "native_snapshots": coordinator["snapshots_received"]})
        except (KeyError, TypeError, ValueError, IndexError, StopIteration) as error:
            check(False, "incomplete/invalid record: " + repr(error), worker)
    operations = {}
    for name in OPERATIONS:
        values = [o["elapsed_ns"] for w in workers for o in w["operations"][name]["observations"]]
        decisions = [w["operations"][name]["decision"] for w in workers]
        verdicts = Counter(d["verdict"] for d in decisions)
        operations[name] = dict(stats(values), budget_ns=EXPECTED_BUDGETS[name],
            verdicts=dict(verdicts), mixed_miss_workers=[w["worker"] for w in workers if w["operations"][name]["decision"].get("miss_kind") == "mixed"],
            all_over_workers=[w["worker"] for w in workers if w["operations"][name]["decision"].get("miss_kind") == "all_over"],
            failing_workers=[w["worker"] for w in workers if w["operations"][name]["decision"]["verdict"] != "pass"],
            verification=stats([o["verification_ns"] for w in workers for o in w["operations"][name]["observations"] if "verification_ns" in o]))
    probes = {name: dict(stats([n for w in workers for n in w["probe_samples_ns"][name]]),
                        cap_ns=cap, binding_for_core=name != "fdatasync64",
                        over_cap_samples=[{"worker": w["worker"], "repeat": repeat, "elapsed_ns": n}
                                          for w in workers for repeat, n in enumerate(w["probe_samples_ns"][name]) if n > cap],
                        over_cap_observations=sum(n > cap for w in workers for n in w["probe_samples_ns"][name]))
              for name, cap in profiles.CAPS_NS.items()}
    admitted = sum(w["core_admission"]["admitted"] for w in workers)
    complete_controls = sum(w["native_rejection_complete"] for w in workers)
    product_count = sum(row["count"] for row in operations.values())
    costs = {key: stats([w[key] for w in workers]) for key in
             ("cli_wall_ns", "gate_total_ns", "preflight_ns", "native_cli_ns", "native_coordinator_ns", "native_collect_ns")}
    costs["warm_startup_ns"] = stats([w["operations"][OPERATIONS[0]]["excluded_stages"].get("startup_ns") for w in workers])
    costs["warm_drain_ns"] = stats([w["operations"][OPERATIONS[0]]["excluded_stages"].get("drain_ns") for w in workers])
    costs["both_commands_ns"] = stats([w["cli_wall_ns"] + w["native_cli_ns"] for w in workers])
    passed = (not errors and len(workers) == 12 and admitted == 12 and product_count == 72
              and all(row["verdicts"] == {"pass": 12} for row in operations.values()) and complete_controls == 12)
    return {"campaign": CAMPAIGN, "run_id": RUN_ID, "shared_revision": SHARED,
            "authority_revision": AUTHORITY, "activation_revision": ACTIVATION,
            "screen_passed": passed, "validation_errors": errors, "failures": failures,
            "workers": len(workers), "core_admitted": admitted, "product_observations": product_count,
            "probe_observations": sum(p["count"] for p in probes.values()),
            "native_rejection_controls_complete": complete_controls,
            "native_storage_operation_observations": 0 if all(w["native_rejection_complete"] for w in workers) else None,
            "operations": operations, "probes": probes, "costs": costs,
            "cpu_models": dict(Counter(w["cpu_model"] for w in workers)),
            "image_versions": dict(Counter(w["image_version"] for w in workers)),
            "mount_sources": dict(Counter(w["mount_source"] for w in workers)),
            "sqlite_versions": dict(Counter(w["sqlite_version"] for w in workers)),
            "artifact_count": len(artifacts), "artifact_zip_bytes_downloaded": provenance["collection"]["artifact_zip_bytes_downloaded"],
            "frozen_sources": frozen, "by_worker": workers}


def report(data):
    ms = lambda n: (f"{n / 1e6:.7f}" if n % 1 else f"{n / 1e6:.6f}") if n is not None else "—"
    lines = ["# Installed shared-package qualification: twelve fresh workers", "",
             f"**Predeclared screen: {'PASS' if data['screen_passed'] else 'BLOCKED'}.** "
             f"Core admission {data['core_admitted']}/12; {data['product_observations']}/72 product observations; "
             f"{data['native_rejection_controls_complete']}/12 complete native rejection controls.", "",
             f"Run: https://github.com/nashspence/all/actions/runs/{RUN_ID} (first attempt, Ubuntu 24.04).", "",
             "## Complete raw operations", "",
             "| Operation | Fixed budget ms | Observations | Raw min ms | Raw median ms | Raw max ms | Pass / miss / unqualified / failed workers |",
             "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for name, row in data["operations"].items():
        counts = " / ".join(str(row["verdicts"].get(k, 0)) for k in ("pass", "miss", "unqualified", "failed"))
        lines.append(f"| {name} | {ms(row['budget_ns'])} | {row['count']} | {ms(row['min_ns'])} | {ms(row['median_ns'])} | {ms(row['max_ns'])} | {counts} |")
    lines += ["", "Each observation executes sixteen real `all_policy.check_repository` calls over the approved valid/invalid/missing workflow fixtures. "
              "The frozen adapter records completion and checks all sixteen outputs. Every raw observation—not a minimum or an average—must fit its unchanged limit. "
              "Median is descriptive only. The two budgets remain experimental demonstration numbers.", "",
              "Warm timing covers parent request through returned completed operation. Cold timing includes a fresh process, fixture creation, import, execution, closed result and completed foreground lifecycle. "
              "Warm startup, verification and final resource teardown are recorded separately. The underlying per-repository output values are not retained in these packets: this analysis verifies the recorded checks and immutable oracle source, not a replay of those output bodies.", "",
              "## Generic preflight", "",
              "| Probe | Observations | Fixed cap ms | Raw min ms | Raw max ms | Over cap | Binding for this core profile |",
              "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for name, row in data["probes"].items():
        lines.append(f"| {name} | {row['count']} | {ms(row['cap_ns'])} | {ms(row['min_ns'])} | {ms(row['max_ns'])} | {row['over_cap_observations']} | {'yes' if row['binding_for_core'] else 'no; diagnostic'} |")
    lines += ["", "Admission was recomputed from the frozen profile implementation and all retained metadata/probe observations. "
              "The synchronization probe cannot grant persistence qualification; it does not bind the selected core API profile. No timing was scaled.", "",
              "## Native storage rejection", "",
              f"The installed collector produced {data['native_rejection_controls_complete']}/12 complete configuration rejections. "
              "Its actual mount reasons were recomputed from retained topology. The packets and CLI exits retain `profile_approved=false` and `physical_persistence_proven=false`; they are not durable-storage passes. "
              "The incompatible roots are rejected before native witness operations run, so this control contains no native storage-operation timing qualification.", "",
              "The control uses a 60-second outer watchdog, separately retaining the package's 300-second deadline and checkpoint-coordinator evidence. "
              "This live rejection check does not exercise timeout handling or prove behavior during a real storage failure.", "",
              "## Cost and excluded stages", "",
              "| Scope | Count | Minimum ms | Median ms | Maximum ms |",
              "| --- | ---: | ---: | ---: | ---: |"]
    labels = {"cli_wall_ns": "Complete common CLI", "preflight_ns": "Generic preflight", "native_cli_ns": "Native rejection CLI",
              "both_commands_ns": "Both complete CLIs", "warm_startup_ns": "Warm worker startup (excluded)", "warm_drain_ns": "Warm final teardown (excluded)"}
    for key, label in labels.items():
        row = data["costs"][key]
        lines.append(f"| {label} | {row['count']} | {ms(row['min_ns'])} | {ms(row['median_ns'])} | {ms(row['max_ns'])} |")
    for name in OPERATIONS:
        row = data["operations"][name]["verification"]
        lines.append(f"| {name} verification (excluded) | {row['count']} | {ms(row['min_ns'])} | {ms(row['median_ns'])} | {ms(row['max_ns'])} |")
    lines += ["", "CLI costs exclude checkout, Python setup, package installation and artifact upload. "
              "These costs do not change product acceptance budgets.", "", "## Observed allocation scope", ""]
    for label, key in (("CPU model", "cpu_models"), ("Ubuntu image version", "image_versions"), ("Native mount source", "mount_sources"), ("SQLite library", "sqlite_versions")):
        lines += [f"| {label} | Workers |", "| --- | ---: |"]
        lines += [f"| {name} | {count} |" for name, count in sorted(data[key].items())]
        lines.append("")
    options = sorted(set.intersection(*(set(w["mount_options"]) for w in data["by_worker"]))) if data["by_worker"] else []
    lines += ["Mount options common to all allocations: `" + ",".join(options) + "`.", "",
              "## Validation, provenance and limits", "",
              f"Validation errors: **{len(data['validation_errors'])}**. Failure IDs: **{data['failures'] or 'none'}**.", "",
              "Diagnostic probe cap exceedances: " + ("; ".join(
                  f"{name}, worker {sample['worker']}, zero-based repeat {sample['repeat']}: {ms(sample['elapsed_ns'])} ms"
                  for name, probe in data["probes"].items() for sample in probe["over_cap_samples"]) or "none") + ". "
              "A nonbinding diagnostic exceedance is retained and does not change the declared core decision.", "",
              f"Shared package/candidate: `{SHARED}`. Authority: `{AUTHORITY}`. Activation workflow: `{ACTIVATION}`.", "",
              "The analyzer checks twelve unique job/runner allocations; run/attempt/source identities; installed module, manifest and adapter hashes; "
              "deterministically serialized raw JSON/packet digests; approved timing boundaries; every recorded output check; and independently recomputed admissions and decisions. "
              f"All {data['artifact_count']} artifact metadata entries are retained. ZIP archive bytes were not downloaded or independently hashed; the analyzed raw JSON was recovered from the original first-attempt job logs.", "",
              "This campaign validates the frozen shared implementation and its real repository-check example on these allocations. "
              "It does not qualify Riverhog or Fishhat, publish a new product budget, establish future-image reliability or long-term false-alarm rates, or certify physical persistence. "
              "The controlled-native infrastructure prerequisite remains unresolved by a rejection result.", "",
              "## Reproduce the pure analysis", "",
              "Use Python 3.11 or newer with PyYAML. Keep the evidence and frozen shared implementation in separate checkouts; the analyzer verifies the specified shared files against their immutable hashes before importing them. It does not run probes or product operations.", "",
              "```sh", "git clone --branch experiment/64-runner-calibration https://github.com/nashspence/all.git evidence",
              "git clone https://github.com/nashspence/all.git shared",
              f"git -C shared checkout --detach {SHARED}",
              "python -m pip install 'PyYAML>=6,<7'",
              "python evidence/experiments/64/v5/common_validation/analyze.py \\",
              '  --shared-checkout "$PWD/shared" \\',
              '  --output "$PWD/common-analysis"', "```", "",
              "The default observation and provenance paths are beside the analyzer in the evidence checkout. No implementation is implicitly loaded from that evidence tree.", ""]
    if data["validation_errors"]:
        lines += ["### Every validation error", ""] + [f"- Worker {r['worker']}: {r['error']}" for r in data["validation_errors"]]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-checkout", type=Path, required=True,
                        help="Explicit checkout/export of the frozen shared revision; source hashes are verified before import")
    parser.add_argument("--observations", type=Path, default=HERE / "observations.json")
    parser.add_argument("--provenance", type=Path, default=HERE / "provenance.json")
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    data = analyze(json.loads(args.observations.read_text()), json.loads(args.provenance.read_text()), args.shared_checkout)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "analysis.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    (args.output / "RESULTS.md").write_text(report(data))
    print(json.dumps({key: data[key] for key in ("screen_passed", "validation_errors", "failures", "workers", "core_admitted", "product_observations", "probe_observations", "native_rejection_controls_complete")}))
    return 0 if data["screen_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
