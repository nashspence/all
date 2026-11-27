import base64
from copy import deepcopy
import hashlib
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import zipfile

from all_policy.performance import refresh_artifacts as artifacts


def archive(filename, packet=b'{"raw":123}\n', unsafe=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as output:
        output.writestr(filename, packet)
        if unsafe:
            output.writestr("../outside", b"never extract")
    return stream.getvalue()


class Fixture:
    headers = {"Authorization": "Bearer secret", "Accept": "application/vnd.github+json"}

    def __init__(self, kind="core"):
        self.rows, self.retained, self.zips = [], {}, {}
        for slot in range(1, 13):
            filename = f"worker-1-{slot}.json"
            packet = (str(slot) + "\n").encode()
            raw = archive("packets/" + filename, packet)
            name = f"profile-core-1-{slot}" if kind == "core" else f"storage-profile-refresh-101-{slot}"
            self.rows.append({"id": slot, "name": name, "expired": False, "size_in_bytes": len(raw),
                              "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                              "workflow_run": {"id": 101}})
            self.retained[name + "/packets/" + filename] = {
                "sha256": hashlib.sha256(packet).hexdigest(), "bytes": len(packet),
                "base64": base64.b64encode(packet).decode()}
            self.zips[slot] = raw

    def get(self, path, **query):
        assert path == "/repos/nashspence/all/actions/runs/101/artifacts"
        assert query == {"per_page": 100, "page": 1}
        return {"total_count": len(self.rows), "artifacts": deepcopy(self.rows)}

    def verify(self, kind="core"):
        with patch.object(artifacts, "_download", side_effect=lambda client, identity, remaining: self.zips[identity]):
            return artifacts.verify(self, 101, kind, self.retained)


class ArtifactTests(unittest.TestCase):
    def test_original_zip_and_worker_bytes_are_both_verified(self):
        for kind in ("core", "storage"):
            with self.subTest(kind=kind):
                records, errors = Fixture(kind).verify(kind)
                self.assertEqual(errors, {})
                self.assertEqual(len(records), 12)
                self.assertTrue(all(record["status"] == "verified" for record in records))

    def test_zip_mismatch_and_local_packet_mismatch_preserve_other_allocations(self):
        fixture = Fixture()
        fixture.rows[0]["digest"] = "sha256:" + "0" * 64
        local = next(value for key, value in fixture.retained.items() if key.endswith("worker-1-2.json"))
        local["base64"] = base64.b64encode(b"changed").decode()
        records, errors = fixture.verify()
        self.assertEqual(set(errors), {(1, 1), (1, 2)})
        self.assertIn("ZIP SHA256 mismatch", errors[(1, 1)])
        self.assertIn("packet differs", errors[(1, 2)])
        self.assertEqual(sum(record["status"] == "verified" for record in records), 10)
        self.assertIn("actual_sha256", records[0])

    def test_missing_duplicate_and_wrong_run_artifacts_are_not_qualification(self):
        fixture = Fixture()
        fixture.rows.pop(0)
        duplicate = dict(fixture.rows[0], id=99)
        fixture.rows.append(duplicate)
        fixture.rows[1]["workflow_run"]["id"] = 999
        _, errors = fixture.verify()
        self.assertEqual(set(errors), {(1, 1), (1, 2), (1, 3)})

    def test_unsafe_zip_and_fixed_expansion_bounds_fail_without_extraction(self):
        fixture = Fixture()
        raw = archive("packets/worker-1-1.json", b"1\n", unsafe=True)
        fixture.zips[1] = raw
        fixture.rows[0].update(size_in_bytes=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
        _, errors = fixture.verify()
        self.assertIn("unsafe", errors[(1, 1)])
        with patch.object(artifacts, "MAX_PACKET", 1):
            _, errors = Fixture().verify()
        self.assertEqual(len(errors), 12)

    def test_storage_redirect_receives_no_repository_credentials(self):
        class Response(io.BytesIO):
            def geturl(self):
                return self.url
        class Opener:
            def __init__(self, location):
                self.location, self.requests = location, []
            def open(self, request, timeout):
                self.requests.append((request, timeout))
                if len(self.requests) == 1:
                    raise HTTPError(request.full_url, 302, "redirect", {"Location": self.location}, None)
                response = Response(b"zip bytes")
                response.url = request.full_url
                return response
        opener = Opener("https://results.blob.core.windows.net/zip?signature=private")
        with patch.object(artifacts, "build_opener", return_value=opener):
            self.assertEqual(artifacts._download(Fixture(), 7, 100), b"zip bytes")
        first, second = opener.requests
        self.assertEqual(first[0].full_url, "https://api.github.com/repos/nashspence/all/actions/artifacts/7/zip")
        self.assertEqual(first[0].headers["Authorization"], "Bearer secret")
        self.assertNotIn("Authorization", second[0].headers)
        self.assertEqual((first[1], second[1]), (10, 10))
        for location in ("http://results.blob.core.windows.net/zip?signature=private",
                         "https://localhost/zip?signature=private",
                         "https://results.blob.core.windows.net.attacker.invalid/zip?signature=private"):
            opener = Opener(location)
            with patch.object(artifacts, "build_opener", return_value=opener):
                with self.assertRaises(artifacts.ArtifactError) as raised:
                    artifacts._download(Fixture(), 7, 100)
            self.assertEqual(len(opener.requests), 1)
            self.assertNotIn("private", str(raised.exception))

    def test_metadata_outage_records_errors_without_discarding_local_packets(self):
        fixture = Fixture()
        before = deepcopy(fixture.retained)
        with patch.object(fixture, "get", side_effect=OSError("network")):
            records, errors = artifacts.verify(fixture, 101, "core", fixture.retained)
        self.assertEqual(len(errors), 12)
        self.assertEqual(fixture.retained, before)
        self.assertEqual(records[0]["error"], "artifact inventory unavailable: OSError")


if __name__ == "__main__":
    unittest.main()
