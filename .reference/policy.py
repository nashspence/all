"""Bind a real verifier call to one key-byte snapshot and independent trust.

The owner supplies signature-family parsing and cryptographic verification.
No signature format, public-key registry or cryptographic primitive is defined.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re


@dataclass(frozen=True)
class VerificationBinding:
    family: str
    public_key_sha256: str
    subject_sha256: str
    signature_sha256: str


def verify_bound(subject, signature, public_key_path, *, expected_family,
                 trusted_key_sha256, identify_family, verify):
    if not isinstance(subject, bytes) or not isinstance(signature, bytes):
        raise TypeError("subject and signature must be exact bytes")
    trust = frozenset(trusted_key_sha256)
    if not expected_family or not trust or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in trust):
        raise ValueError("independent family and full key-byte digests are required")
    family = identify_family(signature)
    if family != expected_family:
        raise ValueError("signature family does not match independently selected authority")
    key = Path(public_key_path).read_bytes()
    if not key:
        raise ValueError("empty public key")
    fingerprint = sha256(key).hexdigest()
    if fingerprint not in trust:
        raise ValueError("actual verification key is outside independent trust")
    # Successful adapters return None; failed crypto must raise. A claimed bool
    # result is not accepted as a verification receipt.
    if verify(subject, signature, key) is not None:
        raise TypeError("cryptographic adapter must complete or raise")
    return VerificationBinding(family, fingerprint, sha256(subject).hexdigest(), sha256(signature).hexdigest())
