# Developer onboarding

- Run `git submodule update --init --checkout` and `python3 checks/submodules.py --checkout`.
- Pin submodules to default-branch commits. Keep cross-repo rules in tests and CI; keep hub prose in this file and `README.md`.
- File a tracking issue and pitch each rule to the maintainer. After approval, add a durable check with strict, issue-linked expected failures for known gaps. Then open focused alignment PRs. Remove the expected failures and close the issue only after all applicable repositories pass.
