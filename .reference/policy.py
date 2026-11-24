"""Exercise an owner's current parser and explicitly retired inputs."""


def assert_hard_cut(parse, *, accepted, retired, rejection):
    if not isinstance(rejection, type) or not issubclass(rejection, Exception) or rejection is Exception:
        raise ValueError("select a specific domain rejection exception")
    accepted, retired = list(accepted), list(retired)
    if not accepted or not retired:
        raise ValueError("current and retired examples are both required")
    for value, expected in accepted:
        actual = parse(value)
        if type(actual) is not type(expected) or actual != expected:
            raise AssertionError("current input changed behavior")
    for value in retired:
        try:
            parse(value)
        except rejection:
            continue
        raise AssertionError("retired input is still accepted")
