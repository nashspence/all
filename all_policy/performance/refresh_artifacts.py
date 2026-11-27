"""Verify original Actions ZIPs against metadata and the retained worker bytes."""
import base64
import hashlib
import io
from pathlib import PurePosixPath
import re
import stat
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

PREFIX = "/repos/nashspence/all"
MAX_BYTES = 64 * 1024**2
MAX_PACKET = 4 * 1024**2
MAX_MEMBERS = 256


class ArtifactError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise ArtifactError(message)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _download(client, artifact_id, remaining):
    opener = build_opener(_NoRedirect())
    url = f"https://api.github.com{PREFIX}/actions/artifacts/{artifact_id}/zip"
    headers = client.headers
    for _ in range(4):
        try:
            with opener.open(Request(url, headers=headers), timeout=10) as response:
                _require(response.geturl() == url, "unexpected artifact redirect")
                data = response.read(remaining + 1)
            _require(len(data) <= remaining, "artifact compressed bytes exceed 64 MiB run bound")
            return data
        except HTTPError as error:
            _require(error.code in {301, 302, 303, 307, 308}, "artifact download HTTP failure")
            url = error.headers.get("Location", "")
            target = urlsplit(url)
            _require(target.scheme == "https" and bool(target.hostname)
                     and target.hostname.endswith((".blob.core.windows.net", ".githubusercontent.com"))
                     and target.username is None and target.password is None
                     and target.port in {None, 443}, "artifact redirect must use approved HTTPS storage")
            # The signed URL comes only from the fixed GitHub API/its storage.
            # Never forward the repository token or API headers to that URL.
            headers = {}
    raise ArtifactError("artifact redirect bound exceeded")


def _inventory(client, run_id):
    rows, total = [], None
    for page in range(1, 21):
        response = client.get(f"{PREFIX}/actions/runs/{run_id}/artifacts", per_page=100, page=page)
        batch, count = response.get("artifacts"), response.get("total_count")
        _require(isinstance(batch, list) and len(batch) <= 100 and type(count) is int
                 and 0 <= count <= 2000 and (total is None or total == count),
                 "invalid artifact inventory")
        total = count
        rows.extend(batch)
        if len(batch) < 100:
            _require(len(rows) == total and all(isinstance(row, dict) for row in rows)
                     and len({row.get("id") for row in rows}) == total,
                     "incomplete or duplicate artifact inventory")
            return rows
    raise ArtifactError("artifact inventory exceeds pagination bound")


def verify(client, run_id, kind, retained, cohorts=1):
    """Return retained verification records and per-slot errors without losing packets."""
    expected = {(cohort, slot): (f"profile-core-{cohort}-{slot}" if kind == "core"
                                else f"storage-profile-refresh-{run_id}-{slot}")
                for cohort in range(1, cohorts + 1) for slot in range(1, 13)}
    records, errors, compressed, expanded = [], {}, 0, 0
    try:
        artifacts = _inventory(client, run_id)
    except Exception as error:
        reason = "artifact inventory unavailable: " + type(error).__name__
        return [{"status": "failed", "error": reason}], dict.fromkeys(expected, reason)
    for key, name in expected.items():
        matches = [row for row in artifacts if row.get("name") == name]
        record = {"name": name, "metadata": matches, "status": "failed"}
        records.append(record)
        try:
            _require(len(matches) == 1, "original artifact missing or duplicated")
            row = matches[0]
            _require(type(row.get("id")) is int and row["id"] > 0
                     and row.get("expired") is False and row.get("workflow_run", {}).get("id") == run_id,
                     "artifact does not identify the original run")
            digest = row.get("digest")
            _require(isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest),
                     "original artifact SHA256 missing")
            _require(type(row.get("size_in_bytes")) is int
                     and 0 < row["size_in_bytes"] <= MAX_BYTES - compressed,
                     "artifact compressed bytes exceed 64 MiB run bound")
            raw = _download(client, row["id"], MAX_BYTES - compressed)
            compressed += len(raw)
            record["actual_sha256"] = hashlib.sha256(raw).hexdigest()
            record["compressed_bytes"] = len(raw)
            _require("sha256:" + record["actual_sha256"] == digest,
                     "original artifact ZIP SHA256 mismatch")
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = archive.infolist()
                _require(len(members) <= MAX_MEMBERS, "artifact ZIP member bound exceeded")
                expanded += sum(member.file_size for member in members)
                _require(expanded <= MAX_BYTES, "artifact expanded bytes exceed 64 MiB run bound")
                for member in members:
                    path = PurePosixPath(member.filename)
                    mode = stat.S_IFMT(member.external_attr >> 16)
                    _require(not path.is_absolute() and ".." not in path.parts
                             and "\\" not in member.filename and "\0" not in member.orig_filename
                             and mode in {0, stat.S_IFREG, stat.S_IFDIR} and not member.flag_bits & 1,
                             "unsafe or encrypted artifact ZIP member")
                filename = f"worker-{key[0]}-{key[1]}.json"
                packets = [member for member in members if PurePosixPath(member.filename).name == filename]
                local = [value for path, value in retained.items() if PurePosixPath(path).name == filename]
                _require(len(packets) == len(local) == 1 and not packets[0].is_dir()
                         and packets[0].file_size <= MAX_PACKET, "worker packet missing, duplicate or oversized")
                packet = archive.read(packets[0])
                retained_bytes = base64.b64decode(local[0]["base64"], validate=True)
                _require(packet == retained_bytes and hashlib.sha256(packet).hexdigest() == local[0]["sha256"],
                         "downloaded worker packet differs from original artifact")
                record["packet_sha256"] = hashlib.sha256(packet).hexdigest()
                record["status"] = "verified"
        except Exception as error:
            reason = str(error) if isinstance(error, ArtifactError) else type(error).__name__
            errors[key] = record["error"] = reason
            if isinstance(error, ArtifactError) and "compressed bytes exceed" in reason:
                compressed = MAX_BYTES
    prefix = "profile-core-" if kind == "core" else f"storage-profile-refresh-{run_id}-"
    unexpected = [row for row in artifacts if isinstance(row.get("name"), str)
                  and row["name"].startswith(prefix) and row["name"] not in expected.values()]
    if unexpected:
        records.append({"status": "failed", "metadata": unexpected, "error": "undeclared campaign artifacts"})
        errors[(1, 1)] = "undeclared campaign artifacts"
    return records, errors
