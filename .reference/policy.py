def assert_authorization_boundary(make_case, refused):
    if not isinstance(refused, type) or not issubclass(refused, Exception) or refused is Exception:
        raise ValueError("a specific domain exception is required")
    for authorized, evidence_valid in ((False, True), (True, False), (False, False)):
        operation, observe = make_case(authorized, evidence_valid)
        before = observe()
        try:
            operation()
        except refused:
            pass
        else:
            raise AssertionError("owner operation did not refuse missing required authority/evidence")
        if observe() != before:
            raise AssertionError("refused operation changed the effect witness")
    operation, observe = make_case(True, True)
    operation()
