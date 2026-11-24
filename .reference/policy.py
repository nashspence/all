import math


def finite_number(value, *, minimum=None, maximum=None):
    if type(value) not in (int, float):
        raise ValueError("a number, excluding bool, is required")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("a finite representable number is required")
    if minimum is not None and value < minimum:
        raise ValueError("number is below its owner-declared minimum")
    if maximum is not None and value > maximum:
        raise ValueError("number exceeds its owner-declared maximum")
    return value


def integer(value, *, minimum=None, maximum=None, allow_integral_float=False):
    if type(value) is not int:
        if not (allow_integral_float and type(value) is float
                and math.isfinite(value) and value.is_integer()):
            raise ValueError("an integer under the declared representation rule is required")
        value = int(value)
    if minimum is not None and value < minimum:
        raise ValueError("integer is below its owner-declared minimum")
    if maximum is not None and value > maximum:
        raise ValueError("integer exceeds its owner-declared maximum")
    return value
