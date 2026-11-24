"""Match each wheel's declared license metadata and bytes to its component owner."""

import email
import re
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class DeclaredLicense:
    expression: str
    files: Mapping[str, bytes]


def _name(value: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", value):
        raise ValueError("invalid distribution identity")
    return re.sub(r"[-_.]+", "-", value).lower()


def _license_path(name: str) -> str:
    path = PurePosixPath(name)
    if not name or not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name or str(path) != name:
        raise ValueError("license filename is not a canonical relative path")
    return name


def check_distribution_licenses(wheels: Iterable[Path], expected: Mapping[str, DeclaredLicense]) -> None:
    declarations = {}
    for name, declaration in expected.items():
        identity = _name(name)
        if identity in declarations:
            raise ValueError("duplicate normalized declared distribution")
        if type(declaration.expression) is not str or not declaration.expression or not declaration.files:
            raise ValueError("owner must declare an expression and license payload")
        for filename, contents in declaration.files.items():
            _license_path(filename)
            if type(contents) is not bytes:
                raise ValueError("license payload must be exact bytes")
        declarations[identity] = declaration
    found = set()
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("duplicate wheel member")
            metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(metadata_names) != 1 or metadata_names[0].count("/") != 1:
                raise ValueError("expected one top-level metadata record")
            metadata_name = metadata_names[0]
            metadata = email.message_from_bytes(archive.read(metadata_name))
            identities = metadata.get_all("Name", [])
            if len(identities) != 1:
                raise ValueError("expected one distribution identity")
            identity = _name(identities[0])
            if identity not in declarations or identity in found:
                raise ValueError("unknown or duplicate distribution")
            found.add(identity)
            declaration = declarations[identity]
            if metadata.get_all("License-Expression", []) != [declaration.expression]:
                raise ValueError("license expression differs from owner declaration")
            declared_files = metadata.get_all("License-File", [])
            if len(declared_files) != len(set(declared_files)) or set(declared_files) != set(declaration.files):
                raise ValueError("License-File metadata differs from owner declaration")
            prefix = metadata_name.removesuffix("METADATA") + "licenses/"
            for filename, contents in declaration.files.items():
                member = prefix + filename
                if member not in names or archive.read(member) != contents:
                    raise ValueError("license payload is missing or differs from owner bytes")
    if found != set(declarations):
        raise ValueError("missing declared distributions")

