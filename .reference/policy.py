def require_formats(checker, cases):
    for name, (accepted, rejected) in cases.items():
        accepted, rejected = tuple(accepted), tuple(rejected)
        if name not in checker.checkers:
            raise ValueError(f"required format checker is unavailable: {name}")
        if not accepted or not rejected:
            raise ValueError(f"required format needs positive and negative examples: {name}")
        if any(not checker.conforms(value, name) for value in accepted):
            raise ValueError(f"required format rejects its accepted examples: {name}")
        if any(checker.conforms(value, name) for value in rejected):
            raise ValueError(f"required format accepts its rejected examples: {name}")
    return checker
