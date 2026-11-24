import re


def _profile(widths, prefix):
    widths = tuple(widths)
    if not widths or any(type(width) is not int or width < 1 for width in widths):
        raise ValueError("positive integer widths required")
    if len(set(widths)) != len(widths) or not isinstance(prefix, str):
        raise ValueError("distinct widths and a literal prefix required")
    return widths


def exact_hex(value, *, widths, prefix=""):
    widths = _profile(widths, prefix)
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    payload = value[len(prefix):]
    return len(payload) in widths and all(char in "0123456789abcdef" for char in payload)


def hex_schema(*, widths, prefix=""):
    widths = _profile(widths, prefix)
    return {
        "type": "string",
        "anyOf": [
            {"minLength": len(prefix) + width, "maxLength": len(prefix) + width,
             "pattern": "^" + re.escape(prefix) + "[0-9a-f]{" + str(width) + "}$"}
            for width in widths
        ],
    }
