.DEFAULT_GOAL := help
.PHONY: help

help:
	@printf '%s\n' \
		'Initialize pinned repositories: git submodule update --init --checkout' \
		'Verify submodule pins: python3 checks/submodules.py --checkout' \
		'Cross-repo parity checks run in GitHub Actions.'
