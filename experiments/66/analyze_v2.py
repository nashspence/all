"""Independent finite-population checks for the new frozen #66 v2 campaign.

No benchmark is executed and no worker verdict, minimum, mean, or normalization
can rescue missing evidence or an operation miss. Probe timing caps are retained
as historical diagnostics only: v2 claims configuration admission, not those
probe latency capabilities. Input is exactly twelve fresh acceptance workers
plus the retained GitHub job manifest {run, source, activation, jobs}. V1 evidence
and verdicts remain governed by the untouched v1 analyzer.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import statistics

PROFILE = "public-linux-x64-4cpu-prepared-ext4-v2"
CAPS = {"cpu_serial": 350_000_000, "cpu_p4": 300_000_000, "sha256": 250_000_000,
        "warm_files": 150_000_000, "fdatasync64": 250_000_000}
LIMITS = {"atomic16_p1": 320_000_000, "atomic16_p2": 320_000_000,
          "atomic16_p4": 320_000_000, "append64_sync": 1_280_000_000,
          "sqlite64_delete_extra": 1_280_000_000, "sqlite64_wal_full": 1_280_000_000,
          "sqlite64_delete_extra_batch": 320_000_000, "sqlite64_wal_full_batch": 320_000_000}
CONSUMERS = {
    "fishhat": {"source": "f96b83dc20f059d62a4363a63c37bb0ef8c642e5",
        "lock": "9bd952bfee4c465e1fb8cf0b8d816361ff508d3c2767078795e0a30fdfb8650d",
        "module": "1d81a2d001b409e27934da94b06d0cf1c37167cf4d703c547ced619097c95acb",
        "adapter": "2b1769a4903d6a99ab29454527bddd21bb550345b69d4b64591824b68d92cd7b"},
    "riverhog": {"source": "be483fd6d567616d5fcd355202d61f1e682efe75",
        "lock": "16b64145aa11bfbd6d2076a7a5adc783ed7d2e000237f9c31e9977ef48815f24",
        "module": "252f7f74ac48affbe73e4bda09baf96a16d7bb59706ed2891e597e1f4bf48cb8",
        "adapter": "d0a38212f2bc2af6dc63df0678e2770e9026564a3bcb5cd9efbfad76440bda48"},
}
HELPER_HASH = "d39da81d384818c2c8a920d78e82a8ac2617378932d345fe74dd94b3ae78b2b3"
ROLES = ("root_loop_a", "root_loop_b")


def obj(value):
    return value if isinstance(value, dict) else {}


def positive(value):
    return type(value) is int and value > 0


def check(errors, condition, label):
    if not condition:
        errors.append(label)


def clean_command(value):
    return obj(value).get("returncode") == 0 and not obj(value).get("timed_out")


def load(path):
    if path.stat().st_size > 16 * 1024**2:
        raise ValueError("record exceeds 16 MiB bound")
    return json.loads(path.read_text())


def stats(values):
    return {"count": len(values), "min_ns": min(values), "max_ns": max(values),
            "median_ns": statistics.median(values), "mean_ns": statistics.mean(values),
            "total_ns": sum(values)} if values else {"count": 0}


def settings(mount):
    options = set(obj(mount).get("effective_ext4_options", []))
    barrier = 0 if options & {"nobarrier", "barrier=0"} else 1 if options & {"barrier", "barrier=1"} else None
    values = {key: [o.split("=", 1)[1] for o in options if o.startswith(key + "=")]
              for key in ("max_batch_time", "data")}
    return (barrier, values["max_batch_time"], values["data"])


def source_info(value, errors, label, expected=None):
    value = obj(value)
    files = obj(value.get("files_sha256"))
    check(errors, bool(files) and all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
                                     for v in files.values()), label + ": module hashes")
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    check(errors, value.get("package_sha256") == digest and value.get("python") == "3.12.16",
          label + ": source aggregate/runtime")
    check(errors, value.get("package") == "nashspence-all" and value.get("module") == "all_policy.performance",
          label + ": shared package identity")
    if expected is not None:
        check(errors, files == expected, label + ": shared module tuple differs")
    return files


def probe(evidence, root, roots, errors, metrics, prefix, command=True, paired=True,
          require_prepared=False, preparation_hash=None, diagnostics=None):
    evidence = obj(evidence)
    check(errors, evidence.get("errors") == [], prefix + ": missing/error probe packet")
    if command:
        check(errors, clean_command(evidence.get("command")), prefix + ": probe command incomplete")
    samples = obj(evidence.get("samples_ns"))
    check(errors, set(samples) == set(CAPS), prefix + ": probe set differs")
    for name, cap in CAPS.items():
        values = samples.get(name, [])
        check(errors, isinstance(values, list) and len(values) == 3, prefix + "/" + name + ": three observations required")
        for repeat, value in enumerate(values if isinstance(values, list) else []):
            check(errors, positive(value), prefix + f"/{name}/{repeat}: invalid raw observation")
            if positive(value):
                metrics["probe/" + name].append(value)
                if value > cap and diagnostics is not None:
                    diagnostics.append({"location": prefix, "probe": name, "repeat": repeat,
                                        "elapsed_ns": value, "legacy_cap_ns": cap})
    for phase in ("metadata", "metadata_after"):
        row = obj(evidence.get(phase)); mount = obj(row.get("mount"))
        valid = (row.get("system") == "Linux" and row.get("machine") in {"x86_64", "amd64"}
                 and row.get("python") == "3.12.16" and row.get("logical_cpus") == 4
                 and row.get("affinity_count") == 4 and positive(row.get("memory_total_bytes"))
                 and row["memory_total_bytes"] >= 14 * 1024**3 and positive(row.get("free_bytes"))
                 and row["free_bytes"] >= 64 * 1024**2 and row.get("root") == root
                 and mount.get("fstype") == "ext4" and mount.get("target") == root
                 and bool(mount.get("source")) and bool(mount.get("options")) and bool(row.get("topology")))
        check(errors, valid, prefix + "/" + phase + ": incompatible/missing metadata")
        quota = row.get("cpu_max")
        if quota and not str(quota).startswith("max "):
            try:
                amount, period = map(int, quota.split())
                check(errors, period > 0 and amount >= 4 * period, prefix + ": CPU quota")
            except (ValueError, AttributeError):
                errors.append(prefix + ": malformed CPU quota")
        memory = row.get("memory_max")
        check(errors, memory in (None, "max") or str(memory).isdigit() and int(memory) >= 14 * 1024**3,
              prefix + ": memory quota")
        if require_prepared:
            check(errors, "prepared_storage" in row, prefix + "/" + phase + ": mandatory prepared custody missing")
        if "prepared_storage" in row:
            prepared = obj(row["prepared_storage"])
            check(errors, prepared.get("errors") == [] and prepared.get("profile") == PROFILE
                  and prepared.get("selected_root") == root and prepared.get("resource_roots") == roots,
                  prefix + "/" + phase + ": prepared custody inspection")
            identity = obj(prepared.get("manifest_identity")); verification = obj(prepared.get("verification"))
            check(errors, identity.get("uid") == identity.get("gid") == 0
                  and identity.get("mode") == 0o400 and identity.get("nlink") == 1
                  and verification.get("status") == "verified" and set(obj(verification.get("mounts"))) == {"a", "b"}
                  and bool(prepared.get("preparation_source_sha256"))
                  and prepared.get("preparation_source_sha256") == prepared.get("current_source_sha256"),
                  prefix + "/" + phase + ": protected manifest/source verification")
            if require_prepared:
                check(errors, bool(preparation_hash) and prepared.get("current_source_sha256") == preparation_hash,
                      prefix + "/" + phase + ": preparation source differs from frozen installed module")
            observed_mount = obj(prepared.get("selected_mount"))
            check(errors, all(observed_mount.get(k) == mount.get(k) for k in
                  ("target", "source", "fstype", "options", "maj:min")),
                  prefix + "/" + phase + ": ordinary/prepared mount evidence differs")
    before, after = obj(evidence.get("metadata")), obj(evidence.get("metadata_after"))
    check(errors, all(before.get(k) == after.get(k) for k in ("root", "device", "mount")),
          prefix + ": mount changed during probe")
    if "prepared_storage" in before:
        a, b = obj(before["prepared_storage"]), obj(after.get("prepared_storage"))
        check(errors, all(a.get(k) and a.get(k) == b.get(k) for k in ("binding_sha256", "manifest_sha256")),
              prefix + ": prepared binding changed")
    if paired and require_prepared:
        check(errors, "prepared_pair" in evidence, prefix + ": mandatory counterpart evidence missing")
    if paired and "prepared_pair" in evidence:
        pair = obj(evidence["prepared_pair"])
        counterpart = next((key for key, value in roots.items() if value != root), None)
        other = obj(pair.get("evidence"))
        check(errors, counterpart is not None and pair.get("counterpart_role") == counterpart
              and pair.get("counterpart_root") == roots.get(counterpart), prefix + ": wrong counterpart")
        probe(other, roots.get(counterpart), roots, errors, metrics, prefix + "/paired", False, False,
              require_prepared, preparation_hash, diagnostics)
        primary = obj(before.get("prepared_storage")); secondary = obj(obj(other.get("metadata")).get("prepared_storage"))
        check(errors, bool(primary.get("manifest_sha256")) and
              primary.get("manifest_sha256") == secondary.get("manifest_sha256"), prefix + ": pair custody differs")


def preparation(record, errors, metrics):
    prep = obj(record.get("preparation")); roots = {key: prep.get(key) for key in ROLES}
    check(errors, prep.get("status") == "cleaned" and prep.get("owned_resources_removed") is True
          and prep.get("errors") == [] and not prep.get("termination_unconfirmed"), "preparation/cleanup incomplete")
    check(errors, prep.get("physical_persistence_proven") is False, "unexpected physical persistence claim")
    setup, cleanup = record.get("setup_outer_ns"), record.get("cleanup_outer_ns")
    check(errors, positive(setup) and positive(cleanup), "missing setup/cleanup clocks")
    if positive(setup) and positive(cleanup):
        total = setup + cleanup
        metrics["cost/setup_cleanup"].append(total)
        check(errors, total <= 60_000_000_000 and record.get("setup_cleanup_ns") == total,
              "setup+cleanup exceeds60s or sum differs")
    original = obj(prep.get("root_original_settings"))
    check(errors, settings(prep.get("root_prepared")) == (1, ["0"], [original.get("data_mode", "").removeprefix("data=")]),
          "backing root barrier/batching/data evidence differs")
    check(errors, settings(prep.get("root_restored")) ==
          (original.get("barrier"), [str(original.get("max_batch_time"))], [original.get("data_mode", "").removeprefix("data=")]),
          "original root options not restored")
    check(errors, settings(prep.get("root_before")) == settings(prep.get("root_restored")) and all(
          obj(prep.get("root_before")).get(key) == obj(prep.get("root_prepared")).get(key)
          == obj(prep.get("root_restored")).get(key) for key in ("source", "target", "maj:min", "fstype")),
          "backing root identity/original options differ")
    images = prep.get("images", [])
    check(errors, isinstance(images, list) and len(images) == 2 and
          {obj(i).get("label") for i in images} == {"a", "b"}, "two distinct image labels required")
    devices = []
    for item in images if isinstance(images, list) else []:
        item = obj(item); loop = obj(item.get("loop_identity")); identity = obj(item.get("image_identity"))
        mount = obj(item.get("mount")); label = item.get("label")
        check(errors, item.get("cleanup") == "removed" and roots.get("root_loop_" + str(label)) == item.get("mountpoint")
              and mount.get("target") == item.get("mountpoint") and settings(mount) == (1, ["0"], ["ordered"]),
              "image/" + str(label) + ": role, mount configuration or cleanup")
        check(errors, loop.get("dio") in (True, 1, "1") and loop.get("ro") in (False, 0, "0")
              and loop.get("back-file") == item.get("image") and loop.get("back-ino") == identity.get("ino")
              and int(loop.get("offset", -1)) == 0 and int(loop.get("sizelimit", -1)) in (0, 256 * 1024**2)
              and identity.get("uid") == identity.get("gid") == 0 and identity.get("mode") == 0o600
              and identity.get("nlink") == 1 and identity.get("size") == 256 * 1024**2
              and identity.get("blocks", 0) * 512 >= 256 * 1024**2,
              "image/" + str(label) + ": allocation/directIO/backing identity")
        devices.append(obj(item.get("mounted_identity")).get("dev"))
    devices.append(obj(prep.get("native_identity")).get("dev"))
    check(errors, None not in devices and len(set(devices)) == 3, "filesystem identities not distinct")
    verifications = prep.get("verifications", [])
    check(errors, isinstance(verifications, list) and len(verifications) >= 2 and all(
          obj(v).get("status") == "verified" and set(obj(obj(v).get("mounts"))) == {"a", "b"}
          for v in verifications), "pre/post actual mount verification incomplete")
    for index, value in enumerate(verifications if isinstance(verifications, list) else []):
        value = obj(value)
        check(errors, value.get("root") == prep.get("root_prepared"), f"mount verification/{index}: backing changed")
        for item in images if isinstance(images, list) else []:
            observed = obj(obj(value.get("mounts")).get(obj(item).get("label")))
            check(errors, observed.get("mount") == obj(item).get("mount")
                  and observed.get("loop") == obj(item).get("loop_identity"),
                  f"mount verification/{index}/{obj(item).get('label')}: actual mount/loop changed")
    return roots


def valid_observations(rows, errors, prefix, metrics, metric, limit=None, repeats=False):
    check(errors, isinstance(rows, list) and len(rows) == 3, prefix + ": exactly three observations required")
    count, misses = 0, []
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        row = obj(row); elapsed = row.get("elapsed_ns")
        valid = row.get("completed") is True and row.get("verified") is True and row.get("error") is None and positive(elapsed)
        check(errors, valid, prefix + f"/{index}: incomplete/wrong/invalid observation")
        if repeats:
            check(errors, row.get("repeat") == index, prefix + f"/{index}: repeat mismatch")
        count += int(valid)
        if positive(elapsed):
            metrics[metric].append(elapsed)
            if limit is not None and elapsed > limit:
                misses.append(index)
    return count, misses


def worker(record, number, args, job, activation, metrics, baseline):
    common, resource, consumers = [], [], []
    probe_diagnostics = []
    github = obj(record.get("github")); collection = obj(record.get("collection"))
    check(common, str(record.get("worker")) == str(number) and record.get("campaign") == args.phase,
          "worker/phase mismatch")
    check(common, record.get("source_revision") == args.source and record.get("python") == "3.12.16",
          "source/runtime mismatch")
    check(common, record.get("profile") == PROFILE and github.get("ImageOS") == "ubuntu24", "profile/image mismatch")
    check(common, github.get("GITHUB_REPOSITORY") == "nashspence/all"
          and github.get("GITHUB_REF") == "refs/heads/experiment/66-native-storage"
          and str(github.get("GITHUB_RUN_ID")) == args.run and str(github.get("GITHUB_RUN_ATTEMPT")) == "1"
          and github.get("GITHUB_SHA") == activation and github.get("STORAGE66_WORKFLOW_SHA") == activation,
          "run/attempt/repository/activation mismatch")
    check(common, obj(job).get("conclusion") == "success", "GitHub job missing or not successful")
    check(resource, record.get("errors") == [] and collection.get("errors") == [], "controller/collection errors")
    check(resource, clean_command(record.get("collection_command")) and clean_command(collection.get("generic_command")),
          "collection/generic command incomplete")
    check(resource, collection.get("postflight_intact") is True, "postflight integrity absent")
    files = source_info(record.get("shared_source"), common, "shared", baseline or None)
    if args.phase == "acceptance" and number == 1:
        controls = obj(record.get("controls"))
        control_log = str(controls.get("stdout", "")) + "\n" + str(controls.get("stderr", ""))
        check(common, controls.get("exit_code") == 0 and "OK" in control_log.splitlines(),
              "frozen shared authority/completion controls missing or unsuccessful")
    roots = preparation(record, resource, metrics)
    for phase in ("preflight", "postflight"):
        decisions = obj(collection.get(phase + "s"))
        check(resource, set(decisions) == set(ROLES), phase + ": both declared roots required")
        for role in ROLES:
            decision = obj(decisions.get(role))
            check(resource, decision.get("admitted") is True and decision.get("reasons") == [], phase + "/" + role + ": unqualified")
            evidence = obj(collection.get("probe_evidence")).get(phase + "-" + role)
            probe(evidence, roots[role], roots, resource, metrics, phase + "/" + role,
                  require_prepared=args.phase == "acceptance", preparation_hash=files.get("prepared_storage.py"),
                  diagnostics=probe_diagnostics)
    generic = obj(collection.get("generic")); operations = obj(generic.get("operations"))
    source_info(generic.get("shared_source"), resource, "generic shared", files)
    check(resource, generic.get("errors") == [] and generic.get("complete") is True and set(operations) == set(LIMITS)
          and generic.get("root") == roots["root_loop_a"], "generic packet/extent/placement")
    generic_count = 0
    for name, limit in LIMITS.items():
        row = obj(operations.get(name))
        check(resource, row.get("limit_ns") == limit, name + ": fixed screen changed")
        count, misses = valid_observations(row.get("observations"), resource, name, metrics, "generic/" + name, limit, True)
        generic_count += count
        resource.extend(name + f"/{i}: raw budget miss" for i in misses)
        for index, sample in enumerate(row.get("observations", [])):
            receipt = obj(obj(sample).get("receipt")); stages = obj(obj(sample).get("stages"))
            check(resource, receipt.get("operation") == name, name + f"/{index}: wrong receipt")
            if name.startswith("atomic"):
                correct = receipt.get("kind") == "atomic" and receipt.get("workers") == int(name[-1]) and receipt.get("completed") == list(range(16))
            elif name == "append64_sync":
                correct = receipt.get("kind") == "append" and receipt.get("acknowledgments") == 64
            else:
                batch, wal = name.endswith("_batch"), "_wal_" in name
                correct = (receipt.get("kind") == "sqlite" and receipt.get("batch") is batch
                    and receipt.get("acknowledgments") == (1 if batch else 64)
                    and receipt.get("journal_mode") == ("WAL" if wal else "DELETE")
                    and receipt.get("synchronous") == ("FULL" if wal else "EXTRA")
                    and receipt.get("checkpoint") == ([0, 0, 0] if wal else None)
                    and receipt.get("legacy_diagnostic") is False and receipt.get("concurrent_connections") == 1)
            check(resource, correct, name + f"/{index}: incorrect operation/acknowledgment extent")
            for key in ("startup_prepare_ns", "verification_reset_ns", "drain_fixture_cleanup_ns"):
                check(resource, positive(stages.get(key)), name + f"/{index}: missing {key}")
                if positive(stages.get(key)):
                    metrics["generic_stage/" + key].append(stages[key])
    consumer_counts, consumer_misses = {}, {}
    selected = obj(collection.get("consumers"))
    check(consumers, set(selected) == set(CONSUMERS), "both consumer packets required")
    for name, pins in CONSUMERS.items():
        call = obj(selected.get(name)); value = obj(call.get("result")); source = obj(value.get("consumer_source"))
        prefix = name + ": "
        check(consumers, clean_command(call.get("command")) and value.get("status") == "complete"
              and value.get("errors") == [] and "worker_error" not in value,
              prefix + "consumer execution incomplete")
        check(consumers, source.get("revision") == pins["source"] and source.get("uv_lock_sha256") == pins["lock"]
              and source.get("tracked_clean") is True and obj(value.get("shared_checkout")).get("revision") == args.source
              and value.get("experiment_revision") == args.source, prefix + "source/dependency pin mismatch")
        source_info(value.get("shared_source_info"), consumers, name + " shared", files)
        provenance = obj(value.get("consumer_provenance")); module = obj(provenance.get("provenance"))
        check(consumers, module.get("source") == pins["source"] and module.get("module_sha256") == pins["module"]
              and str(module.get("python", "")).startswith("3.12.16 "), prefix + "normal product module/runtime pin")
        check(consumers, value.get("approved_files") == {"experiments/66/consumer_cases.py": HELPER_HASH,
              f"experiments/66/{name}_adapter.py": pins["adapter"]}, prefix + "reviewed binding hashes")
        if args.phase == "acceptance":
            prepared = obj(provenance.get("prepared_resource"))
            before = obj(obj(obj(collection.get("probe_evidence")).get("preflight-root_loop_a")).get("metadata"))
            canonical = obj(before.get("prepared_storage"))
            check(consumers, prepared.get("errors") == [] and prepared.get("resource_roots") == roots
                  and prepared.get("selected_root") == roots["root_loop_a"]
                  and prepared.get("current_source_sha256") == files.get("prepared_storage.py")
                  and bool(prepared.get("manifest_sha256"))
                  and prepared.get("manifest_sha256") == canonical.get("manifest_sha256"),
                  prefix + "actual worker did not inspect the same prepared resource")
        count, misses = valid_observations(value.get("observations"), consumers, name, metrics, "consumer/" + name, 320_000_000)
        consumer_counts[name], consumer_misses[name] = count, misses
        for index, sample in enumerate(value.get("observations", [])):
            elapsed = obj(sample).get("verification_ns")
            check(consumers, positive(elapsed), prefix + f"verification/{index}: missing elapsed cost")
            if positive(elapsed):
                metrics["consumer_stage/" + name + "/verification_ns"].append(elapsed)
        verification = value.get("verification", [])
        check(consumers, isinstance(verification, list) and len(verification) == 3, prefix + "three retained verifications required")
        for repeat, evidence in enumerate(verification if isinstance(verification, list) else []):
            evidence = obj(evidence)
            valid = evidence.get("verified") is True and evidence.get("publications") == 16
            if name == "fishhat":
                head = hashlib.sha256(f"{provenance.get('fixture_id')}:{repeat * 16 + 15}".encode()).hexdigest()
                valid = valid and evidence.get("fresh_head") == head
            else:
                valid = valid and evidence.get("retained_files_verified") == (repeat + 1) * 16 and evidence.get("bytes_per_file") == 4096
            check(consumers, valid, prefix + f"verification/{repeat}: extent/head/bytes differ")
        stages = obj(value.get("excluded_stages"))
        check(consumers, not stages.get("error"), prefix + "worker lifecycle error")
        for key in ("startup_ns", "drain_ns"):
            check(consumers, positive(stages.get(key)), prefix + "missing " + key)
            if positive(stages.get(key)):
                metrics["consumer_stage/" + name + "/" + key].append(stages[key])
    for field, value in (("controller", record.get("total_ns")), ("bootstrap", obj(record.get("bootstrap")).get("bootstrap_wall_ns"))):
        if positive(value):
            metrics["cost/" + field].append(value)
    return {"worker": number, "runner": github.get("RUNNER_NAME"), "image": github.get("ImageVersion"),
            "job_id": obj(job).get("id"), "common_failures": common, "resource_failures": resource,
            "consumer_failures": consumers, "resource_pass": not common and not resource,
            "both_consumers_correct": not common and not consumers, "generic_valid_observations": generic_count,
            "consumer_valid_observations": consumer_counts, "consumer_engineering_misses": consumer_misses,
            "legacy_probe_cap_exceedances": probe_diagnostics}, files


def analyze(args):
    failures, metrics, workers, baseline = [], defaultdict(list), [], None
    try:
        manifest = obj(load(args.manifest or args.records / "manifest.json"))
    except Exception as error:
        failures.append("missing/invalid GitHub manifest: " + type(error).__name__ + ": " + str(error))
        manifest = {}
    check(failures, str(manifest.get("run")) == args.run and manifest.get("source") == args.source, "manifest run/source mismatch")
    activation = manifest.get("activation")
    check(failures, isinstance(activation, str) and re.fullmatch(r"[0-9a-f]{40}", activation), "missing activation identity")
    jobs = manifest.get("jobs", []); expected_names = {f"storage-{i}" for i in range(1, args.expected + 1)}
    check(failures, isinstance(jobs, list) and len(jobs) == args.expected and
          {obj(j).get("name") for j in jobs} == expected_names and
          len({obj(j).get("id") for j in jobs}) == args.expected and
          all(str(obj(j).get("id", "")).isdigit() for j in jobs), "exact unique GitHub job population required")
    jobs = {obj(j).get("name"): obj(j) for j in (jobs if isinstance(jobs, list) else [])}
    expected_files = {f"worker-{i}.json" for i in range(1, args.expected + 1)}
    check(failures, {p.name for p in args.records.glob("worker-*.json")} == expected_files, "missing/extra worker files")
    for number in range(1, args.expected + 1):
        try:
            record = load(args.records / f"worker-{number}.json")
            result, files = worker(record, number, args, jobs.get(f"storage-{number}"), activation, metrics, baseline)
            baseline = baseline or files
        except Exception as error:
            result = {"worker": number, "resource_pass": False, "both_consumers_correct": False,
                      "common_failures": [type(error).__name__ + ": " + str(error)],
                      "resource_failures": [], "consumer_failures": []}
        workers.append(result)
    names = [w.get("runner") for w in workers]
    check(failures, None not in names and len(set(names)) == args.expected, "distinct worker runner identities required")
    resource_passed = sum(w["resource_pass"] for w in workers)
    consumer_passed = sum(w["both_consumers_correct"] for w in workers)
    qualified = not failures and resource_passed == args.expected
    applicable = not failures and consumer_passed == args.expected
    return {"schema": "all.storage66.independent-analysis/v2", "profile": PROFILE,
        "source": args.source, "run": args.run,
        "phase": args.phase, "expected_workers": args.expected, "resource_workers_passed": resource_passed,
        "consumer_workers_correct": consumer_passed, "population_failures": failures,
        "resource_qualification": "passed" if qualified and args.phase == "acceptance" else "not_qualified",
        "both_consumers_applicable": applicable and qualified and args.phase == "acceptance",
        "profile_approved_by_analyzer": False, "physical_persistence_proven": False,
        "expected_generic_observations": args.expected * 24, "expected_consumer_observations": args.expected * 6,
        "generic_valid_observations": sum(w.get("generic_valid_observations", 0) for w in workers),
        "consumer_valid_observations": sum(sum(w.get("consumer_valid_observations", {}).values()) for w in workers),
        "consumer_engineering_misses": {name: [f"worker-{w['worker']}/{repeat}" for w in workers
            for repeat in w.get("consumer_engineering_misses", {}).get(name, [])] for name in CONSUMERS},
        "legacy_probe_caps_ns": CAPS, "probe_latency_caps_are_acceptance_conditions": False,
        "legacy_probe_cap_exceedances": [{"worker": w["worker"], **entry} for w in workers
            for entry in w.get("legacy_probe_cap_exceedances", [])],
        "images": dict(Counter(w.get("image") or "unavailable" for w in workers)), "workers": workers,
        "metrics": {key: stats(value) for key, value in sorted(metrics.items())},
        "interpretation": "V2 admits the declared resource configuration and requires complete correct raw probes; probe latencies are diagnostic. Every actual generic storage operation must meet its unchanged fixed maximum. Means/minima never rescue an operation miss. Consumer320ms misses remain separate. V1 verdicts are unchanged. No crash/release proof follows."}


def brief(result):
    lines = ["# Prepared storage v2 campaign analysis", "",
             f"Run {result['run']}; phase **{result['phase']}**; source `{result['source']}`.", "",
             f"**Resource qualification: {result['resource_qualification']}.** "
             f"Resource workers passing: {result['resource_workers_passed']}/{result['expected_workers']}; "
             f"workers with both consumers correct: {result['consumer_workers_correct']}/{result['expected_workers']}.", "",
             f"Complete verified generic observations: {result['generic_valid_observations']}/{result['expected_generic_observations']}; "
             f"consumer observations: {result['consumer_valid_observations']}/{result['expected_consumer_observations']}.", "",
             "| Observed quantity | Count | Minimum ms | Maximum ms | Median ms |", "|---|---:|---:|---:|---:|"]
    for name, values in result["metrics"].items():
        if not name.startswith("probe/"):
            lines.append(f"| {name} | {values['count']} | {values['min_ns']/1e6:.3f} | {values['max_ns']/1e6:.3f} | {values['median_ns']/1e6:.3f} |")
    lines += ["", "## Historical probe caps: diagnostics only", "",
              "These caps belonged to v1. V2 claims no probe latency guarantee; all probe observations and correctness remain required.", "",
              "| Probe | Count | Maximum ms | Historical cap ms | Above historical cap |",
              "|---|---:|---:|---:|---:|"]
    exceedances = result["legacy_probe_cap_exceedances"]
    for name, cap in CAPS.items():
        values = result["metrics"].get("probe/" + name, {"count": 0})
        maximum = f"{values['max_ns']/1e6:.3f}" if values["count"] else "missing"
        lines.append(f"| {name} | {values['count']} | {maximum} | {cap/1e6:.3f} | {sum(e['probe'] == name for e in exceedances)} |")
    if exceedances:
        lines.append("")
    for entry in exceedances:
        lines.append(f"- Diagnostic worker-{entry['worker']}/{entry['location']}/{entry['probe']}/{entry['repeat']}: "
                     f"{entry['elapsed_ns']/1e6:.3f} ms; historical cap {entry['legacy_cap_ns']/1e6:.3f} ms.")
    lines += ["", "## Failures and consumer target misses", ""]
    messages = list(result["population_failures"])
    for worker_result in result["workers"]:
        for field in ("common_failures", "resource_failures", "consumer_failures"):
            messages.extend(f"worker-{worker_result['worker']}: {reason}" for reason in worker_result[field])
    for name, misses in result["consumer_engineering_misses"].items():
        if misses:
            messages.append(name + "320ms engineering misses: " + ", ".join(misses))
    lines.extend("- " + message for message in messages)
    if not messages:
        lines.append("No failures or consumer engineering target misses.")
    lines += ["", result["interpretation"], "",
              "This analysis recomputes recorded numerical/completion gates and source identities; it does not rerun native operations. "
              "GitHub job outcomes come from the separately retained manifest. Approval remains a versioned repository decision.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--expected", type=int, default=12)
    parser.add_argument("--phase", choices=("acceptance",), default="acceptance")
    parser.add_argument("--source", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.expected != 12 or re.fullmatch(r"[0-9a-f]{40}", args.source) is None:
        parser.error("v2 requires exactly12 fresh acceptance workers and a full lowercase source commit SHA")
    result = analyze(args)
    output = args.output or args.records / "analysis-v2.json"
    report = args.report or args.records / "RESULTS-v2.md"
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    text = brief(result); report.write_text(text); print(text)
    return 0 if result["resource_qualification"] == "passed" and result["both_consumers_applicable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
