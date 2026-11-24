import json
import math


def loads(text: str, *, object_root: bool = False):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def finite(token):
        value = float(token)
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        return value

    def reject_constant(token):
        raise ValueError(f"non-JSON numeric constant: {token}")

    value = json.loads(text, object_pairs_hook=pairs, parse_float=finite,
                       parse_constant=reject_constant)
    if object_root and not isinstance(value, dict):
        raise ValueError("JSON object root required")
    return value
