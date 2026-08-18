"""Command-line conformance runner for ACN implementations."""

import argparse, base64, json, sys
from pathlib import Path

from . import (
    ContractError,
    parse_a2a_message,
    validate_envelope,
    verify_envelope_signature,
)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def report(ok, operation, path, error=None):
    value = {
        "conformant": ok,
        "operation": operation,
        "path": str(path),
        "specVersion": "0.1",
    }
    if error:
        value["error"] = {"code": "acn.conformance.failed", "detail": str(error)}
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(prog="acn-conformance")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("path")
    a2a = sub.add_parser("validate-a2a")
    a2a.add_argument("path")
    verify = sub.add_parser("verify")
    verify.add_argument("path")
    verify.add_argument("--public-key", required=True)
    suite = sub.add_parser("suite")
    suite.add_argument("directory")
    args = parser.parse_args(argv)
    results = []
    paths = (
        [Path(args.path)]
        if hasattr(args, "path")
        else sorted(Path(args.directory).glob("*.json"))
    )
    for path in paths:
        try:
            value = load(path)
            if args.command == "validate-a2a":
                parse_a2a_message(value)
            else:
                validate_envelope(value)
                if args.command == "verify":
                    key = base64.urlsafe_b64decode(
                        args.public_key + "=" * (-len(args.public_key) % 4)
                    )
                    verify_envelope_signature(value, key)
            results.append(report(True, args.command, path))
        except (OSError, ValueError, ContractError, json.JSONDecodeError) as exc:
            results.append(report(False, args.command, path, exc))
    output = {
        "conformant": all(item["conformant"] for item in results),
        "results": results,
    }
    print(json.dumps(output, separators=(",", ":")))
    return 0 if output["conformant"] else 1


if __name__ == "__main__":
    sys.exit(main())
