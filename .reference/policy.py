CASES = (
    ({}, "checkpoint"),
    ({"saved": 119}, "continue"),
    ({"cost": 40}, "continue"),
    ({"charged": 130}, "continue"),
    ({"reserved": 130}, "continue"),
    ({"remaining": 20}, "continue"),
    ({"attempts": 100}, "checkpoint"),
    ({"replay_safe": False}, "continue"),
    ({"mandatory": True, "saved": 0, "remaining": 0}, "required-work"),
)


def assert_recovery_budget(decide):
    baseline = dict(useful=1000, saved=240, cost=20, remaining=500,
                    charged=0, reserved=0, attempts=0,
                    replay_safe=True, mandatory=False)
    for changes, expected in CASES:
        case = baseline | changes
        actual = decide(case)
        if actual != expected:
            raise AssertionError((changes, expected, actual))
