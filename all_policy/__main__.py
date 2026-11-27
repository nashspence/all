import argparse
import os
import sys

from .audit import audit
from .protocol import SOURCE_REPOSITORY, check_repository


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "performance":
        from .performance.__main__ import main as performance_main
        return performance_main(argv[1:])
    if argv and argv[0] == "performance-status":
        from .performance.approval import main as approval_main
        return approval_main(argv[1:])
    parser = argparse.ArgumentParser(prog="all-policy")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("path", nargs="?", default=".")
    check.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    inventory = commands.add_parser("audit")
    inventory.add_argument("--owner", default=SOURCE_REPOSITORY.split("/")[0])
    commands.add_parser("performance", help="run an approved absolute performance contract")
    commands.add_parser("performance-status", help="read current shared profile approval")
    args = parser.parse_args(argv)
    if args.command == "check":
        errors = check_repository(args.path, args.repository)
        for error in errors:
            print(f"FAIL {error}")
        if not errors:
            print(f"PASS {args.repository or args.path}")
        return int(bool(errors))

    results = audit(
        args.owner,
        token=os.environ.get("GITHUB_TOKEN"),
        inventory_token=os.environ.get("ALL_REPOS_TOKEN"),
    )
    for result in results:
        print(f"{'FAIL' if result.errors else 'PASS'} {result.repository}"
              + (f": {'; '.join(result.errors)}" if result.errors else ""))
    return int(not results or any(result.errors for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
