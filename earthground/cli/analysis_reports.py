"""CLI entry points for strap and thermal analysis reports."""

from __future__ import annotations

import sys

from earthground.cli.compile_project import CompileProjectError, compile_design
from earthground.schematic import SchematicValidationError


def configure_straps_parser(parser) -> None:
    parser.add_argument(
        "project",
        nargs="?",
        default=".",
        help="Earthground project directory (defaults to current directory)",
    )


def configure_thermal_parser(parser) -> None:
    parser.add_argument(
        "project",
        nargs="?",
        default=".",
        help="Earthground project directory (defaults to current directory)",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Destination CSV path",
    )


def _load(project, command):
    try:
        return compile_design(project)
    except (CompileProjectError, SchematicValidationError, OSError) as exc:
        print(f"earthground {command}: error: {exc}", file=sys.stderr)
        return None


def run_straps_args(args) -> int:
    design = _load(args.project, "straps")
    if design is None:
        return 2
    report = design.check_straps()
    if not report.results:
        print("No strap pins declared")
        return 0
    for result in report.results:
        ratio = "?" if result.ratio is None else str(result.ratio)
        level = result.level or "UNKNOWN"
        determining = (
            ""
            if not result.determining_components
            else f" [{', '.join(result.determining_components)}]"
        )
        print(
            f"{result.refdes}.{result.pin:<16} {ratio:<24} "
            f"{level:<8} {result.message}{determining}"
        )
    return 0 if report.is_valid else 1


def run_thermal_args(args) -> int:
    design = _load(args.project, "thermal")
    if design is None:
        return 2
    report = design.thermal_report()
    try:
        destination = report.write_csv(args.output)
    except OSError as exc:
        print(f"earthground thermal: error: {exc}", file=sys.stderr)
        return 2
    unknown = sum(row.status.value != "Pass" for row in report.rows)
    print(
        f"Wrote {len(report.rows)} thermal rows to {destination} ({unknown} unresolved)"
    )
    return 0 if unknown == 0 else 1
