from pathlib import PurePosixPath
import stat
import zipfile


def typing_errors(wheel, inline_packages):
    errors = []
    with zipfile.ZipFile(wheel) as archive:
        members = archive.infolist()
        for package in inline_packages:
            path = PurePosixPath(package)
            if not package or not path.parts or str(path) != package or path.is_absolute() or ".." in path.parts:
                raise ValueError("expected a canonical package path")
            marker = f"{package}/py.typed"
            matches = [item for item in members if item.filename == marker]
            if len(matches) != 1:
                errors.append(f"{marker}: expected exactly one packaged type marker")
            elif matches[0].is_dir() or stat.S_IFMT(matches[0].external_attr >> 16) not in (0, stat.S_IFREG):
                errors.append(f"{marker}: expected a regular file")
    return tuple(errors)
