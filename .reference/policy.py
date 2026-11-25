"""One candidate shared RFC 8785 encoder, not a second serialization algorithm."""
import hashlib
import math

import rfc8785

VERSION = "0.1.4"
SAFE_INTEGER = 2**53 - 1


def _validate(value, active):
    kind = type(value)
    if value is None or kind is bool:
        return
    if kind is str:
        for character in value:
            code = ord(character)
            if 0xD800 <= code <= 0xDFFF or 0xFDD0 <= code <= 0xFDEF or code & 0xFFFF >= 0xFFFE:
                raise ValueError("invalid I-JSON Unicode scalar")
    elif kind is int:
        if abs(value) > SAFE_INTEGER:
            raise ValueError("exact integer outside safe range; use an explicit string codec")
    elif kind is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite binary64 value")
    elif kind in (list, dict):
        if id(value) in active:
            raise ValueError("cyclic JSON value")
        active.add(id(value))
        try:
            if kind is list:
                for item in value:
                    _validate(item, active)
            else:
                for key, item in value.items():
                    if type(key) is not str:
                        raise ValueError("object names must be strings")
                    _validate(key, active)
                    _validate(item, active)
        finally:
            active.remove(id(value))
    else:
        raise ValueError("expected a JSON value")


def canonical_bytes(value):
    """Serialize admitted values; raw JSON must be admitted before calling this."""
    if rfc8785.__version__ != VERSION:
        raise ValueError("unexpected RFC 8785 implementation version")
    _validate(value, set())
    return rfc8785.dumps(value)


def canonical_sha256(value):
    """Digest the JCS value, not arbitrary original file bytes or a signed envelope."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_canonical(raw, admit):
    """Verify exact received canonical bytes using the real strict admission boundary."""
    if type(raw) is not bytes:
        raise ValueError("canonical input must be bytes")
    value = admit(raw)
    if canonical_bytes(value) != raw:
        raise ValueError("input is not canonical JCS")
    return value
