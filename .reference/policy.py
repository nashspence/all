def assert_policy_participates(run_suite, break_policy, restore_policy, diagnostic):
    before = run_suite()
    if before.returncode != 0:
        raise AssertionError("baseline suite does not pass")
    try:
        break_policy()
        after = run_suite()
        output = (after.stdout or "") + (after.stderr or "")
        if after.returncode == 0 or diagnostic not in output:
            raise AssertionError("ordinary suite did not observe the policy violation")
    finally:
        restore_policy()
    if run_suite().returncode != 0:
        raise AssertionError("restored suite does not pass")
