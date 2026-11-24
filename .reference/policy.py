from pathlib import Path, PurePosixPath
import subprocess


def checkout_errors(root: str | Path, revision: str, paths) -> tuple[str, ...]:
    root = Path(root).resolve()
    commit = subprocess.check_output(
        ['git', '-C', str(root), 'rev-parse', '--verify', revision + '^{commit}'], text=True
    ).strip()
    failures = []
    for name in paths:
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or str(relative) != name:
            raise ValueError('fingerprint inputs must be normalized repository-relative paths')
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            failures.append(f'{name}: fingerprint input is not a contained regular file')
            continue
        try:
            expected = subprocess.check_output(
                ['git', '-C', str(root), 'show', f'{commit}:{name}'], stderr=subprocess.DEVNULL
            )
            actual = path.read_bytes()
        except (OSError, subprocess.CalledProcessError):
            failures.append(f'{name}: fingerprint input is missing from commit or checkout')
            continue
        if actual != expected:
            failures.append(f'{name}: checkout bytes differ from the named commit')
    return tuple(failures)
