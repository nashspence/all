from hashlib import sha256
from pathlib import Path


def loaded_digest(module, expected_sha256):
    origin = getattr(getattr(module, "__spec__", None), "origin", None)
    filename = getattr(module, "__file__", None)
    if not origin or not filename or Path(origin).resolve() != Path(filename).resolve():
        raise ValueError("module has no unambiguous file origin")
    path = Path(origin).resolve(strict=True)
    if path.suffix != ".py":
        raise ValueError("owner adapter required for this loader")
    actual = sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError("loaded implementation differs from expected source")
    return actual
