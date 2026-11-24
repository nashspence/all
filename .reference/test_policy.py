import tempfile
import unittest
import zipfile
from pathlib import Path

from policy import DeclaredLicense, check_distribution_licenses


class ArtifactLicenseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.expected = {"example": DeclaredLicense("Apache-2.0", {"LICENSE": b"owner legal bytes\n"})}

    def wheel(self, name="example", expression="Apache-2.0", header="LICENSE", payload=b"owner legal bytes\n", payload_name="LICENSE", suffix=""):
        path = self.root / f"{name}{suffix}.whl"
        prefix = f"{name}-1.dist-info/"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(prefix + "METADATA", f"Name: {name}\nLicense-Expression: {expression}\nLicense-File: {header}\n")
            if payload is not None:
                archive.writestr(prefix + "licenses/" + payload_name, payload)
        return path

    def test_independently_licensed_components_match_their_owners(self):
        first = self.wheel()
        second = self.wheel(name="another", expression="MIT", payload=b"other legal bytes\n")
        declarations = {**self.expected, "another": DeclaredLicense("MIT", {"LICENSE": b"other legal bytes\n"})}
        check_distribution_licenses([first, second], declarations)

    def test_metadata_alone_cannot_substitute_for_legal_bytes(self):
        with self.assertRaisesRegex(ValueError, "owner bytes"):
            check_distribution_licenses([self.wheel(payload=b"wrong text")], self.expected)

    def test_missing_payload_fails(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            check_distribution_licenses([self.wheel(payload=None)], self.expected)

    def test_license_expression_must_match_owning_component(self):
        with self.assertRaisesRegex(ValueError, "expression"):
            check_distribution_licenses([self.wheel(expression="MIT")], self.expected)

    def test_declared_license_filename_is_not_ignored(self):
        with self.assertRaisesRegex(ValueError, "License-File"):
            check_distribution_licenses([self.wheel(header="OTHER")], self.expected)

    def test_duplicate_distribution_cannot_hide_missing_component(self):
        first = self.wheel()
        second = self.wheel(suffix="-duplicate")
        with self.assertRaisesRegex(ValueError, "duplicate distribution"):
            check_distribution_licenses([first, second], self.expected)

    def test_complete_output_set_is_required(self):
        with self.assertRaisesRegex(ValueError, "missing declared"):
            check_distribution_licenses([], self.expected)

    def test_escaping_owner_license_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "relative path"):
            check_distribution_licenses([], {"example": DeclaredLicense("MIT", {"../LICENSE": b"text"})})


if __name__ == "__main__":
    unittest.main()
