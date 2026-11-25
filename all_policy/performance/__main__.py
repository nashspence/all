"""The required workflow supplies approval and storage arguments, not PR inputs."""
import argparse
import json

from .contracts import load_authority
from .runner import run_suite


def main(argv=None):
    parser = argparse.ArgumentParser(prog="all-policy-performance")
    parser.add_argument("--authority", required=True)
    parser.add_argument("--approved-revision", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--storage", action="append", required=True, metavar="PROFILE=PATH")
    args = parser.parse_args(argv)
    try:
        roots = {}
        for item in args.storage:
            profile, path = item.split("=", 1)
            if profile in roots or not path:
                raise ValueError("storage profiles must have one explicit path")
            roots[profile] = path
        authority = load_authority(args.authority, args.approved_revision, args.repository)
        result = run_suite(authority, args.subject, roots)
    except Exception as error:
        result = {"verdict": "failed", "error": type(error).__name__ + ": " + str(error)}
    print(json.dumps(result, sort_keys=True))
    return {"pass": 0, "miss": 1, "unqualified": 2, "failed": 3}[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
