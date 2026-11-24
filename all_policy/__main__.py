import argparse
import os

from .audit import audit
from .protocol import SOURCE_REPOSITORY, check_repository


def main(argv=None):
    parser = argparse.ArgumentParser(prog="all-policy")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("path", nargs="?", default=".")
    check.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    inventory = commands.add_parser("audit")
    inventory.add_argument("--owner", default=SOURCE_REPOSITORY.split("/")[0])
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
