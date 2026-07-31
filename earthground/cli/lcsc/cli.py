from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Optional, Sequence

from earthground.cli.lcsc.database import (
    LcscDatabaseError,
    get_database_path,
    lookup_many,
)


def configure_lcsc_parser(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="lcsc_command", required=True)
    lookup = commands.add_parser(
        "lookup",
        help="Find LCSC IDs by exact manufacturer part number",
    )
    lookup.set_defaults(lcsc_handler=_run_lookup)
    lookup.add_argument(
        "mpn",
        nargs="+",
        help="One or more manufacturer part numbers",
    )
    lookup.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Earthground project root (defaults to upward discovery)",
    )
    lookup.add_argument(
        "--config",
        type=pathlib.Path,
        help="Config file path (defaults to .earthground/config.yaml)",
    )
    output = lookup.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Return JSON")
    output.add_argument(
        "--id-only",
        action="store_true",
        help="Print only matching C-prefixed LCSC IDs",
    )


def _run_lookup(args: argparse.Namespace) -> int:
    database_path = get_database_path(args.project_root, args.config)
    results = lookup_many(database_path, args.mpn)
    found_all = all(result["matches"] for result in results)

    if args.json:
        print(json.dumps({"results": results}, indent=2, sort_keys=True))
    elif args.id_only:
        for result in results:
            for match in result["matches"]:
                print(match["lcsc_id"])
    else:
        for result in results:
            matches = result["matches"]
            if not matches:
                print(
                    f"No LCSC part found for MPN: {result['query']}",
                    file=sys.stderr,
                )
                continue
            for match in matches:
                print(f"MPN: {match['mpn']}")
                print(f"LCSC ID: {match['lcsc_id']}")
                print(f"Package: {match['package']}")
                print(f"Description: {match['description']}")
    return 0 if found_all else 1


def run_parsed_args(args: argparse.Namespace) -> int:
    try:
        return args.lcsc_handler(args)
    except LcscDatabaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="earthground lcsc",
        description="Query the configured LCSC component database",
    )
    configure_lcsc_parser(parser)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return run_parsed_args(args)


if __name__ == "__main__":
    raise SystemExit(main())
