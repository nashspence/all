"""Shared preparation and inspection of owned native ext4 timing resources.

This prepares a timing resource; it does not certify physical power-loss survival
or replace either product's failure/custody qualification.  No unowned device is
formatted.  The root filesystem's data mode is never changed.  setup()/cleanup()
supervise all target I/O in a child with a parent-controlled total deadline.
Keep this module, its interpreter, and report_path on responsive control storage
outside the test mounts.  A stalled control filesystem cannot enforce a deadline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time


BASE = Path("/var/lib/all-policy-66")
IMAGE_BYTES = 256 * 1024 * 1024
SCHEMA = "all-prepared-native-storage/1"
PROFILE_ID = "public-linux-x64-4cpu-prepared-ext4-v2"
MANIFEST_NAME = "resource.json"
MAX_MANIFEST_BYTES = 1024 * 1024
MOUNT_OPTIONS = "barrier=1,data=ordered,max_batch_time=0,nosuid,nodev,noatime,errors=remount-ro"


class PreparationError(RuntimeError):
    def __init__(self, message, context):
        super().__init__(message)
        self.context = context


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _save(report, context):
    if report is None:
        return
    report = Path(report)
    with tempfile.NamedTemporaryFile(mode="w", dir=report.parent,
                                     prefix=report.name + ".", delete=False) as out:
        temporary = out.name
        os.fchmod(out.fileno(), 0o644)
        json.dump(context, out, indent=2, sort_keys=True)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, report)


def _mark(context, report, stage):
    context["stage"] = stage
    _save(report, context)


def _command(context, report, argv, timeout=30, optional=False):
    """Per-command limits supplement the supervising parent's total deadline."""
    entry = {"argv": list(map(str, argv)), "status": "started"}
    context.setdefault("commands", []).append(entry)
    _mark(context, report, "command: " + str(argv[0]))
    start = time.perf_counter_ns()
    try:
        result = subprocess.run(entry["argv"], text=True, capture_output=True,
                                timeout=timeout, check=False)
        entry.update(returncode=result.returncode, stdout=result.stdout[:131072],
                     stderr=result.stderr[:32768], status="completed")
        _require(optional or result.returncode == 0,
                 f"command failed ({result.returncode}): {entry['argv']}: {result.stderr[:2000]}")
        return result.stdout
    except BaseException as error:
        entry["error"] = type(error).__name__ + ": " + str(error)
        entry["status"] = "failed"
        raise
    finally:
        entry["elapsed_ns"] = time.perf_counter_ns() - start
        _save(report, context)


def _identity(path):
    info = os.lstat(path)
    return {"dev": info.st_dev, "ino": info.st_ino, "mode": stat.S_IMODE(info.st_mode),
            "uid": info.st_uid, "gid": info.st_gid, "size": info.st_size,
            "blocks": info.st_blocks, "nlink": info.st_nlink,
            "kind": stat.S_IFMT(info.st_mode), "rdev": info.st_rdev}


def _same_identity(path, expected, *, regular=False):
    got = _identity(path)
    _require(all(got[k] == expected[k] for k in ("dev", "ino", "uid", "gid", "kind")),
             "owned object identity changed: " + str(path))
    _require(got["uid"] == 0 and got["gid"] == 0, "owned object no longer root-owned")
    if regular:
        _require(got["kind"] == stat.S_IFREG and got["mode"] == 0o600 and got["nlink"] == 1,
                 "image is not an exclusively owned regular file")
        _require(got["size"] == IMAGE_BYTES and got["blocks"] * 512 >= IMAGE_BYTES,
                 "image is not fully allocated at the declared size")
    return got


def _protected_directory(path, *, private=False):
    path = Path(path)
    for item in (*reversed(path.parents), path):
        info = os.lstat(item)
        _require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
                 "non-directory/symlink in protected ancestry: " + str(item))
        _require(info.st_uid == 0 and info.st_gid == 0 and not info.st_mode & 0o022,
                 "writable or non-root protected ancestry: " + str(item))
    if private:
        _require(stat.S_IMODE(os.lstat(path).st_mode) == 0o700,
                 "private directory must have mode 0700")


def _mount(context, report, path):
    data = json.loads(_command(context, report,
        ["findmnt", "--json", "--target", str(path), "--output", "TARGET,SOURCE,FSTYPE,OPTIONS,MAJ:MIN"]))
    rows = data.get("filesystems", [])
    _require(len(rows) == 1, "ambiguous mount for " + str(path))
    row = rows[0]
    device = Path("/sys/dev/block") / row["maj:min"]
    row["sysfs_path"] = str(device.resolve(strict=True))
    if row["fstype"] == "ext4":
        # This proc interface prints effective defaults, unlike mountinfo.
        option_file = Path("/proc/fs/ext4") / device.resolve().name / "options"
        row["effective_ext4_options"] = option_file.read_text().split()
    return row


def _ext4_settings(mount):
    options = set(mount.get("effective_ext4_options", []))
    _require(mount["fstype"] == "ext4" and options, "actual ext4 option evidence required")
    barrier = 0 if options & {"nobarrier", "barrier=0"} else 1 if options & {"barrier", "barrier=1"} else None
    batch = [o.split("=", 1)[1] for o in options if o.startswith("max_batch_time=")]
    data = [o for o in options if o.startswith("data=")]
    _require(barrier is not None and len(batch) == 1 and len(data) == 1,
             "cannot establish explicit effective ext4 settings")
    return {"barrier": barrier, "max_batch_time": int(batch[0]), "data_mode": data[0]}


def _topology(context, report, path):
    mount = _mount(context, report, path)
    devices = json.loads(_command(context, report,
        ["lsblk", "--json", "--bytes", "--output", "NAME,KNAME,MAJ:MIN,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL,ROTA"]))
    queues = {}
    # Record the entire visible chain: root may be a partition or device mapper.
    for block in sorted(Path("/sys/class/block").iterdir()):
        values = {}
        for name in ("write_cache", "fua", "rotational", "logical_block_size", "physical_block_size"):
            item = block / "queue" / name
            if item.exists():
                values[name] = item.read_text()[:2048].strip()
        for name in ("backing_file", "dio", "offset", "sizelimit"):
            item = block / "loop" / name
            if item.exists():
                values["loop_" + name] = item.read_text()[:8192].strip()
        slaves = block / "slaves"
        if slaves.exists():
            values["slaves"] = sorted(p.name for p in slaves.iterdir())
        if values:
            queues[block.name] = values
    return {"mount": mount, "block_devices": devices, "sysfs": queues,
            "kernel": platform.release(), "machine": platform.machine(),
            "kvm_device_present": os.path.exists("/dev/kvm"),
            "kvm_device_accessible": os.access("/dev/kvm", os.R_OK | os.W_OK),
            "kvm_usable_not_tested": True, "physical_persistence_proven": False}


def _guard(context):
    _require(os.geteuid() == 0 and os.getegid() == 0, "must run as root on the disposable worker")
    expected = context["expected_repository"]
    refs = context["allowed_refs"]
    _require(isinstance(expected, str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", expected),
             "explicit repository allowlist required")
    _require(refs and all(isinstance(r, str) and r.startswith("refs/heads/") for r in refs),
             "explicit branch-ref allowlist required")
    wanted = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
              "RUNNER_OS": "Linux", "ImageOS": "ubuntu24", "GITHUB_REPOSITORY": expected}
    _require(all(os.environ.get(k) == v for k, v in wanted.items()),
             "not the explicitly authorized GitHub-hosted Ubuntu 24 repository context")
    _require(os.environ.get("GITHUB_REF") in refs, "branch is not explicitly allowed")
    event = os.environ.get("GITHUB_EVENT_NAME")
    _require(event in {"push", "workflow_dispatch"} or
             (event == "schedule" and os.environ.get("GITHUB_REF") == "refs/heads/main"),
             "only trusted push/dispatch or explicitly allowlisted main-ref schedules are allowed")
    _require(platform.machine() == "x86_64", "requires x86_64")
    release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines()
                   if "=" in line)
    _require(release.get("ID", "").strip('"') == "ubuntu" and
             release.get("VERSION_ID", "").strip('"') == "24.04", "requires actual Ubuntu 24.04")
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        _require(re.fullmatch(r"[1-9][0-9]*", os.environ.get(name, "")), "missing real run identity")
    _require(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(context["worker_id"])), "invalid worker identity")
    observed = {key: os.environ.get(key) for key in (
        *wanted, "GITHUB_REF", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "RUNNER_NAME")}
    if context.get("github"):
        _require(all(context["github"].get(key) == observed.get(key) for key in
            ("GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "RUNNER_NAME")),
            "ownership context belongs to a different runner/run/source")
    context["github"] = observed


def _associated(context, report, image):
    raw = _command(context, report, ["losetup", "--json", "--list", "--associated", str(image),
        "--output", "NAME,BACK-FILE,BACK-INO,BACK-MAJ:MIN,DIO,OFFSET,SIZELIMIT,RO"])
    return json.loads(raw).get("loopdevices", [])


def _loop_identity(context, report, item, *, require_configuration=True):
    file_info = _same_identity(item["image"], item["image_identity"], regular=True)
    rows = _associated(context, report, item["image"])
    _require(len(rows) == 1, "expected exactly one loop association for the owned image")
    row = rows[0]
    device = row["name"]
    _require(re.fullmatch(r"/dev/loop[0-9]+", device), "not a loop device")
    if item.get("device"):
        _require(item["device"] == device, "loop device identity changed")
    _require(Path(row["back-file"]).resolve(strict=True) == Path(item["image"]), "wrong loop backing file")
    _require(int(row["back-ino"]) == file_info["ino"], "loop backing inode changed")
    _require(str(row["back-maj:min"]) == f"{os.major(file_info['dev'])}:{os.minor(file_info['dev'])}",
             "loop backing filesystem changed")
    if require_configuration:
        _require(row["dio"] in (True, 1, "1") and row["ro"] in (False, 0, "0"), "loop must be writable direct I/O")
    _require(int(row["offset"]) == 0 and int(row["sizelimit"]) in (0, IMAGE_BYTES), "unexpected loop range")
    info = os.stat(device)
    _require(stat.S_ISBLK(info.st_mode), "loop path is not a block device")
    if item.get("rdev") is not None:
        _require(item["rdev"] == info.st_rdev, "loop device number changed")
    item.update(device=device, rdev=info.st_rdev, loop_identity=row)
    return row


def _setup(context, report):
    _mark(context, report, "guard")
    _guard(context)
    _mark(context, report, "root inspection")
    root_before = _mount(context, report, "/")
    _require(root_before["target"] == "/", "root target mismatch")
    settings = _ext4_settings(root_before)
    context["root_before"] = root_before
    context["root_original_settings"] = settings
    context["root_restore_options"] = [f"barrier={settings['barrier']}",
                                       f"max_batch_time={settings['max_batch_time']}"]
    context["root_change_attempted"] = True
    _mark(context, report, "enable root barriers")
    _command(context, report, ["mount", "-o", "remount,barrier=1,max_batch_time=0", "/"])
    root_after = _mount(context, report, "/")
    _require(root_before["maj:min"] == root_after["maj:min"] and root_before["source"] == root_after["source"],
             "root backing changed")
    _require(_ext4_settings(root_after) == {**settings, "barrier": 1, "max_batch_time": 0},
             "root did not accept the fixed barrier/batching configuration")
    context["root_prepared"] = root_after
    _mark(context, report, "create protected ownership root")
    _protected_directory(BASE.parent)
    try:
        BASE.mkdir(mode=0o700)
    except FileExistsError:
        pass
    _protected_directory(BASE, private=True)
    name = f"{context['github']['GITHUB_RUN_ID']}-{context['github']['GITHUB_RUN_ATTEMPT']}-{context['worker_id']}-{secrets.token_hex(8)}"
    session = BASE / name
    context["session_root"] = str(session)
    _mark(context, report, "reserve unique ownership directory")
    session.mkdir(mode=0o700)
    _protected_directory(session, private=True)
    context["session_identity"] = _identity(session)
    context["images"] = []
    native = session / "native"
    native.mkdir(mode=0o700)
    context["native_root"] = str(native)
    context["native_identity"] = _identity(native)
    _require(os.stat(session).st_dev == os.stat("/").st_dev, "images must reside on the prepared root filesystem")
    for label in ("a", "b"):
        image = session / f"{label}.img"
        mountpoint = session / f"{label}.mount"
        item = {"label": label, "image": str(image), "mountpoint": str(mountpoint)}
        context["images"].append(item)
        _mark(context, report, "reserve owned image " + label)
        fd = os.open(image, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        item["image_identity"] = _identity(image)
        mountpoint.mkdir(mode=0o700)
        item["mountpoint_identity"] = _identity(mountpoint)
        _command(context, report, ["dd", "if=/dev/zero", "of=" + str(image), "bs=1M", "count=256",
                                    "conv=notrunc,fsync", "status=none"], timeout=60)
        _same_identity(image, item["image_identity"], regular=True)
        item["image_identity"] = _identity(image)
        _require(not _associated(context, report, image), "new image already has a loop association")
        device = _command(context, report, ["losetup", "--find", "--show", "--nooverlap",
            "--direct-io=on", "--sector-size", "512", str(image)]).strip()
        item["device"] = device
        # Identity is rechecked immediately before the only destructive command.
        _loop_identity(context, report, item)
        _command(context, report, ["mkfs.ext4", "-F", "-q", "-b", "4096", "-m", "0", "-E",
            "lazy_itable_init=0,lazy_journal_init=0,nodiscard", "-L", "ALL66_" + label.upper(), device], timeout=60)
        _loop_identity(context, report, item)
        _command(context, report, ["mount", "-t", "ext4", "-o", MOUNT_OPTIONS, device, str(mountpoint)])
        os.chmod(mountpoint, 0o700)
        os.chown(mountpoint, 0, 0)
        _protected_directory(mountpoint, private=True)
        actual = _mount(context, report, mountpoint)
        _require(actual["target"] == str(mountpoint) and
                 actual["maj:min"] == f"{os.major(item['rdev'])}:{os.minor(item['rdev'])}",
                 "wrong actual mounted device")
        _require(_ext4_settings(actual) == {"barrier": 1, "max_batch_time": 0, "data_mode": "data=ordered"},
                 "owned mount is not the declared configuration")
        _require({"nosuid", "nodev", "noatime"} <= set(actual["options"].split(",")),
                 "missing required mount restrictions")
        item["mounted_identity"] = _identity(mountpoint)
        item["mount"] = actual
        context["root_loop_" + label] = str(mountpoint)
        _mark(context, report, "owned mount ready " + label)
    _require(len({os.stat(context[k]).st_dev for k in ("root_loop_a", "root_loop_b", "native_root")}) == 3,
             "prepared targets must have three distinct filesystem device identities")
    context["topology"] = {key: _topology(context, report, context[key])
                           for key in ("root_loop_a", "root_loop_b", "native_root")}
    context["storage_semantics"] = "prepared host-native Linux sync API; two separate filesystems share the same host/backing failure domain"
    context["physical_persistence_proven"] = False
    context["status"] = "prepared"
    _write_manifest(context, report)


def _cleanup(context, report):
    _mark(context, report, "cleanup guard")
    _guard(context)
    if context.get("session_root") and not context.get("owned_resources_removed"):
        session = Path(context["session_root"])
        _require(session.parent == BASE, "ownership root outside the fixed base")
        _protected_directory(session, private=True)
        _same_identity(session, context["session_identity"])
        for item in reversed(context.get("images", [])):
            image, mountpoint = Path(item["image"]), Path(item["mountpoint"])
            _require(image.parent == session and mountpoint.parent == session, "foreign ownership manifest path")
            if image.exists():
                # An interrupted dd can leave a partial owned image. Never format
                # or detach by size alone; inode/device/owner still must match.
                _same_identity(image, item["image_identity"])
                rows = _associated(context, report, image)
                if rows:
                    _loop_identity(context, report, item, require_configuration=False)
                    actual = _mount(context, report, mountpoint)
                    if actual["target"] == str(mountpoint):
                        _require(actual["maj:min"] == f"{os.major(item['rdev'])}:{os.minor(item['rdev'])}",
                                 "refusing to unmount an unowned device")
                        _command(context, report, ["umount", "--", str(mountpoint)], timeout=30)
                    # Recheck exact association immediately before detaching.
                    _loop_identity(context, report, item, require_configuration=False)
                    _command(context, report, ["losetup", "--detach", item["device"]])
                    _require(not _associated(context, report, image), "loop remained associated after detach")
                _same_identity(image, item["image_identity"])
                image.unlink()
            if mountpoint.exists():
                _same_identity(mountpoint, item["mountpoint_identity"])
                mountpoint.rmdir()
            item["cleanup"] = "removed"
            _save(report, context)
        native = Path(context["native_root"])
        _require(native == session / "native", "foreign native cleanup subtree")
        if native.exists():
            _same_identity(native, context["native_identity"])
            # Refuse to recurse into any additional mount, even within our path.
            mounts = Path("/proc/self/mountinfo").read_text().splitlines()
            _require(not any(len(line.split()) > 4 and
                (line.split()[4] == str(native) or line.split()[4].startswith(str(native) + "/"))
                for line in mounts), "unexpected mount inside native cleanup subtree")
            shutil.rmtree(native)
        if context.get("manifest_path"):
            manifest = Path(context["manifest_path"])
            _require(manifest.parent == session and manifest.name == MANIFEST_NAME,
                     "foreign protected manifest path")
            if manifest.exists():
                _same_identity(manifest, context["manifest_identity"])
                manifest.unlink()
        _same_identity(session, context["session_identity"])
        session.rmdir()
        context["owned_resources_removed"] = True
    if context.get("root_change_attempted"):
        now = _mount(context, report, "/")
        before = context["root_before"]
        _require(now["maj:min"] == before["maj:min"] and now["source"] == before["source"],
                 "refusing to restore a different root filesystem")
        current = _ext4_settings(now)
        original = context["root_original_settings"]
        _require(current in (original, {**original, "barrier": 1, "max_batch_time": 0}),
                 "root settings changed outside this helper; refusing to overwrite them")
        if current != original:
            _command(context, report, ["mount", "-o", "remount," + ",".join(context["root_restore_options"]), "/"])
        restored = _mount(context, report, "/")
        _require(_ext4_settings(restored) == original, "original root settings were not restored")
        context["root_restored"] = restored
    context["status"] = "cleaned"


def _verify(context, report):
    """Reobserve the prepared resource; no mutation, timing pass or approval."""
    _mark(context, report, "verification guard")
    _guard(context)
    _require(context.get("session_root") and not context.get("owned_resources_removed"),
             "no live prepared ownership context")
    _require(context.get("root_prepared") and len(context.get("images", [])) == 2,
             "incomplete prepared resource manifest")
    images = context["images"]
    _require({item.get("label") for item in images} == {"a", "b"} and
             len({item.get("image") for item in images}) == 2 and
             len({item.get("mountpoint") for item in images}) == 2,
             "prepared resource requires exactly two distinct a/b image/mount bindings")
    for item in images:
        session = Path(context["session_root"])
        label = item["label"]
        _require(item["image"] == str(session / f"{label}.img") and
                 item["mountpoint"] == str(session / f"{label}.mount") and
                 context.get("root_loop_" + label) == item["mountpoint"],
                 "prepared resource role/path mapping changed")
    snapshot = {"status": "started", "mounts": {}}
    context.setdefault("verifications", []).append(snapshot)
    _mark(context, report, "verify prepared root")
    now = _mount(context, report, "/")
    snapshot["root"] = now
    prepared = context["root_prepared"]
    _require(all(now.get(key) == prepared.get(key) for key in
                 ("target", "source", "fstype", "maj:min", "sysfs_path")),
             "prepared root mount identity changed")
    _require(_ext4_settings(now) == {**context["root_original_settings"],
                                     "barrier": 1, "max_batch_time": 0},
             "prepared root barrier/batching/data settings changed")
    _require(set(now["effective_ext4_options"]) == set(prepared["effective_ext4_options"]) and
             set(now["options"].split(",")) == set(prepared["options"].split(",")),
             "prepared root effective mount options changed")
    session = Path(context["session_root"])
    _require(session.parent == BASE, "ownership root outside the fixed base")
    _protected_directory(session, private=True)
    _same_identity(session, context["session_identity"])
    for item in context["images"]:
        image, mountpoint = Path(item["image"]), Path(item["mountpoint"])
        _require(image.parent == session and mountpoint.parent == session,
                 "foreign path in ownership manifest")
        _mark(context, report, "verify owned mount " + item["label"])
        original_loop = dict(item["loop_identity"])
        current_loop = _loop_identity(context, report, dict(item))
        observed = {"loop": current_loop}
        snapshot["mounts"][item["label"]] = observed
        _require(current_loop == original_loop, "prepared loop association/configuration changed")
        _protected_directory(mountpoint, private=True)
        observed["identity"] = _same_identity(mountpoint, item["mounted_identity"])
        actual = _mount(context, report, mountpoint)
        observed["mount"] = actual
        original_mount = item["mount"]
        _require(all(actual.get(key) == original_mount.get(key) for key in
                     ("target", "source", "fstype", "maj:min", "sysfs_path")),
                 "prepared loop mount identity changed")
        _require(_ext4_settings(actual) == {"barrier": 1, "max_batch_time": 0, "data_mode": "data=ordered"},
                 "prepared loop synchronization settings changed")
        _require(set(actual["effective_ext4_options"]) == set(original_mount["effective_ext4_options"]) and
                 set(actual["options"].split(",")) == set(original_mount["options"].split(",")),
                 "prepared loop effective options changed")
        _save(report, context)
    _protected_directory(context["native_root"], private=True)
    snapshot["native_identity"] = _same_identity(context["native_root"], context["native_identity"])
    _require(len({os.stat(context[key]).st_dev for key in ("root_loop_a", "root_loop_b", "native_root")}) == 3,
             "prepared target filesystem identities are no longer distinct")
    snapshot["status"] = "verified"
    snapshot["profile_approved"] = False
    context["status"] = "verified"


def _source_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _write_manifest(context, report):
    """Publish immutable setup custody inside the protected resource directory."""
    manifest = Path(context["session_root"]) / MANIFEST_NAME
    context["manifest_path"] = str(manifest)
    context["profile_id"] = PROFILE_ID
    context["preparation_source_sha256"] = _source_hash()
    _mark(context, report, "publish protected resource manifest")
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    context["manifest_identity"] = _identity(manifest)
    _save(report, context)
    keys = ("schema", "profile_id", "preparation_source_sha256", "manifest_path", "manifest_identity",
            "expected_repository", "allowed_refs", "worker_id", "github", "session_root", "session_identity",
            "root_before", "root_original_settings", "root_restore_options", "root_change_attempted",
            "root_prepared", "native_root", "native_identity", "root_loop_a", "root_loop_b", "images")
    packet = {key: context[key] for key in keys}
    packet.update(status="prepared", commands=[], errors=[], profile_approved=False,
                  physical_persistence_proven=False)
    raw = (json.dumps(packet, indent=2, sort_keys=True) + "\n").encode()
    _require(len(raw) <= MAX_MANIFEST_BYTES, "protected manifest too large")
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(manifest.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    context["manifest_sha256"] = hashlib.sha256(raw).hexdigest()


def _load_manifest(path):
    path = Path(os.path.abspath(path))
    _require(path.name == MANIFEST_NAME and path.parent.parent == BASE,
             "manifest must be at the canonical protected resource path")
    _protected_directory(path.parent, private=True)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        _require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_gid == 0 and
                 stat.S_IMODE(info.st_mode) == 0o400 and info.st_nlink == 1 and
                 0 < info.st_size <= MAX_MANIFEST_BYTES,
                 "invalid protected manifest owner, type, permissions or size")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        _require(len(raw) <= MAX_MANIFEST_BYTES, "protected manifest exceeds its bound")
    finally:
        os.close(fd)
    context = json.loads(raw)
    _require(context.get("schema") == SCHEMA and context.get("profile_id") == PROFILE_ID and
             context.get("status") == "prepared", "wrong protected resource schema/profile/state")
    _require(context.get("preparation_source_sha256") == _source_hash(),
             "resource was prepared by a different shared implementation")
    _require(context.get("manifest_path") == str(path) and context.get("session_root") == str(path.parent),
             "protected manifest path/ownership root mismatch")
    _same_identity(path, context["manifest_identity"])
    context["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    return context


def _load_partial_report(path):
    """Recover only root-owned failure evidence; never invent missing identities."""
    requested = Path(os.path.abspath(path))
    path = requested.parent.resolve(strict=True) / requested.name
    _require(not path.is_relative_to(BASE), "partial report must be on external control storage")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        _require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_gid == 0 and
                 stat.S_IMODE(info.st_mode) == 0o644 and info.st_nlink == 1 and
                 0 < info.st_size <= 8 * MAX_MANIFEST_BYTES,
                 "partial report requires original root-owned bounded regular evidence")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(8 * MAX_MANIFEST_BYTES + 1)
        _require(len(raw) <= 8 * MAX_MANIFEST_BYTES, "partial report exceeds its bound")
    finally:
        os.close(fd)
    context = json.loads(raw)
    _require(context.get("schema") == SCHEMA and context.get("profile_id") == PROFILE_ID and
             context.get("preparation_source_sha256") == _source_hash() and
             context.get("report_path") == str(path), "partial report source/path/profile mismatch")
    _require(context.get("status") in {"setup_failed", "verify_failed", "cleanup_failed"},
             "partial cleanup requires a retained failed phase")
    _require(not context.get("termination_unconfirmed"),
             "cannot reclaim resources while the failed child may still be running")
    return context


def inspect(root):
    """Read actual configuration and canonical custody; never accept a caller flag.

    This performs read-only findmnt/losetup queries and filesystem inspection.
    Its caller owns the outer deadline. No output, mount or device is modified.
    """
    result = {"profile": PROFILE_ID, "errors": [], "physical_persistence_proven": False}
    try:
        root = Path(root).resolve(strict=True)
        relative = root.relative_to(BASE)
        _require(len(relative.parts) >= 2, "target is not inside an owned prepared mount")
        context = _load_manifest(BASE / relative.parts[0] / MANIFEST_NAME)
        _verify(context, None)
        roles = {key: Path(context[key]) for key in ("root_loop_a", "root_loop_b")}
        selected = [key for key, path in roles.items() if root == path or root.is_relative_to(path)]
        _require(len(selected) == 1, "target is not on either prepared loop filesystem")
        selected = selected[0]
        actual = _mount(context, None, root)
        label = "a" if selected == "root_loop_a" else "b"
        enrolled = next(item for item in context["images"] if item["label"] == label)
        _require(actual["target"] == context[selected] and actual["maj:min"] == enrolled["mount"]["maj:min"],
                 "actual target is not the enrolled filesystem")
        verification = context["verifications"][-1]
        result.update(manifest_path=context["manifest_path"], manifest_sha256=context["manifest_sha256"],
            manifest_identity=_identity(context["manifest_path"]),
            preparation_source_sha256=context["preparation_source_sha256"],
            current_source_sha256=_source_hash(), resource_roots={k: str(v) for k, v in roles.items()},
            selected_role=selected, selected_root=str(root), selected_mount=actual,
            github=context["github"], verification=verification)
        binding = {"manifest_sha256": context["manifest_sha256"], "root": verification["root"],
                   "mounts": {k: {"loop": v["loop"], "mount": v["mount"]}
                              for k, v in verification["mounts"].items()},
                   "selected_role": selected, "selected_mount": actual}
        result["binding_sha256"] = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    except Exception as error:
        result["errors"].append(type(error).__name__ + ": " + str(error))
    return result


def _worker(phase, report):
    context = json.loads(Path(report).read_text())
    start = time.perf_counter_ns()
    try:
        {"setup": _setup, "verify": _verify, "cleanup": _cleanup}[phase](context, report)
    except BaseException as error:
        context["status"] = phase + "_failed"
        context.setdefault("errors", []).append(type(error).__name__ + ": " + str(error))
        if phase == "verify" and context.get("verifications"):
            context["verifications"][-1]["status"] = "failed"
    finally:
        context.setdefault("phase_elapsed_ns", {})[phase] = time.perf_counter_ns() - start
        if phase == "verify" and context.get("verifications"):
            context["verifications"][-1]["elapsed_ns"] = context["phase_elapsed_ns"][phase]
        _save(report, context)


def _supervise(phase, context, report_path, timeout_s):
    _require(0 < timeout_s <= 300, "phase timeout must be within (0,300] seconds")
    requested = Path(os.path.abspath(report_path))
    report = requested.parent.resolve(strict=True) / requested.name
    _require(not report.is_relative_to(BASE), "report must be outside the owned/test tree")
    context["phase"] = phase
    context["stage"] = "starting supervised " + phase
    context["control_storage_requirement"] = "responsive external report directory, interpreter and helper source"
    if phase == "setup" or context.get("report_path") != str(report):
        fd = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        os.close(fd)
    context["report_path"] = str(report)
    _save(report, context)
    start = time.monotonic()
    child = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                              "_worker", phase, str(report)], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    failure = None
    try:
        child.wait(timeout=timeout_s)
        if child.returncode:
            failure = f"{phase} child exited {child.returncode}"
    except BaseException as error:
        failure = type(error).__name__ + ": " + str(error)
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            pass
    result = json.loads(report.read_text())
    result.setdefault("supervisor_elapsed_ns", {})[phase] = int((time.monotonic() - start) * 1e9)
    if failure:
        result["status"] = phase + "_failed"
        result.setdefault("errors", []).append(failure)
        result["termination_unconfirmed"] = child.poll() is None
    _save(report, result)
    if result.get("status") != {"setup": "prepared", "verify": "verified", "cleanup": "cleaned"}[phase]:
        raise PreparationError("; ".join(result.get("errors", ["incomplete supervised phase"])), result)
    return result


def setup(expected_repository, allowed_refs, worker_id, report_path, setup_timeout_s=180):
    """Prepare exactly two private loop mounts; return the retained ownership context.

    On failure, PreparationError.context and report_path retain progress for cleanup.
    The caller freezes the explicit repo/branch allowlist in its reviewed workflow.
    """
    context = {"schema": SCHEMA, "expected_repository": expected_repository,
               "allowed_refs": list(allowed_refs), "worker_id": str(worker_id),
               "status": "initial", "errors": [], "commands": [],
               "profile_id": PROFILE_ID, "preparation_source_sha256": _source_hash(),
               "profile_approved": False, "physical_persistence_proven": False}
    return _supervise("setup", context, report_path, setup_timeout_s)


def cleanup(context, report_path, cleanup_timeout_s=120):
    """Remove only resources bound by the manifest and restore our two root options."""
    _require(context.get("schema") == SCHEMA, "wrong ownership manifest schema")
    _require(not context.get("termination_unconfirmed"),
             "cannot reclaim resources while a failed child may still be running")
    return _supervise("cleanup", dict(context), report_path, cleanup_timeout_s)


def verify(context, report_path, verify_timeout_s=60):
    """Supervised pre/postflight check of the same prepared resource and options."""
    _require(context.get("schema") == SCHEMA, "wrong ownership manifest schema")
    _require(context.get("status") in {"prepared", "verified"},
             "verification requires a successful prepared context; earlier failure cannot be retried away")
    return _supervise("verify", dict(context), report_path, verify_timeout_s)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("setup", "verify", "cleanup"):
        child = commands.add_parser(name)
        child.add_argument("--repository", required=True)
        child.add_argument("--allowed-ref", action="append", required=True,
                           help="Exact authorized refs/heads/...; never derive from unreviewed candidate input")
        child.add_argument("--report", required=True, help="Evidence outside test mounts on healthy control storage")
        child.add_argument("--timeout", type=float, default={"setup": 180, "verify": 60, "cleanup": 120}[name])
        if name == "setup":
            child.add_argument("--worker", required=True)
        elif name == "verify":
            child.add_argument("--manifest", required=True, help="Canonical root-owned resource.json from setup")
        else:
            source = child.add_mutually_exclusive_group(required=True)
            source.add_argument("--manifest", help="Canonical root-owned resource.json from setup")
            source.add_argument("--partial-report", help="Original root-owned failed-phase evidence when no complete manifest exists")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            context = setup(args.repository, args.allowed_ref, args.worker, args.report, args.timeout)
        else:
            context = (_load_manifest(args.manifest) if args.manifest
                       else _load_partial_report(args.partial_report))
            _require(context["expected_repository"] == args.repository and
                     set(context["allowed_refs"]) == set(args.allowed_ref),
                     "requested repository/ref scope differs from protected setup custody")
            context = {"verify": verify, "cleanup": cleanup}[args.command](context, args.report, args.timeout)
    except (OSError, ValueError, RuntimeError) as error:
        failure = {"status": args.command + "_failed", "error": str(error), "profile_approved": False}
        if args.command == "setup" and isinstance(error, PreparationError):
            # Partial setup may not have published a usable canonical manifest.
            # Retain the original failure and attempt only manifest-bound cleanup.
            try:
                finished = cleanup(error.context, args.report, cleanup_timeout_s=120)
                failure["cleanup_status"] = finished["status"]
            except (OSError, ValueError, RuntimeError) as cleanup_error:
                failure["cleanup_error"] = str(cleanup_error)
        print(json.dumps(failure), file=sys.stderr)
        return 2
    print(json.dumps({"status": context["status"], "manifest": context.get("manifest_path"),
        "root_loop_a": context.get("root_loop_a"), "root_loop_b": context.get("root_loop_b"),
        "report": context["report_path"], "profile_approved": False}))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "_worker":
        _worker(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(main())
