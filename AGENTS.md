# Developer onboarding

- Run `git submodule update --init --checkout` and `python3 checks/submodules.py --checkout`.
- Pin submodules to default-branch commits. Keep parity tests in each repository’s own suite and verify their presence and PR CI wiring here.
- File and pitch a tracking issue. After approval, add a strict, issue-linked expected failure for any missing test, then open focused test-only PRs. Clear expected failures and close the issue once the pinned tests and their PR lanes are verified.
