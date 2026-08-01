"""Earthground's hierarchical command-line interface."""

from __future__ import annotations

import argparse
from typing import Optional, Sequence

from earthground.cli.add_skills import run_parsed_args as run_skills_args
from earthground.cli.compile_project import (
    configure_compile_parser,
    run_parsed_args as run_compile_args,
)
from earthground.cli.export_kicad import (
    configure_kicad_export_parser,
    run_parsed_args as run_kicad_export_args,
)
from earthground.cli.generate_kicad_footprints import (
    configure_catalog_parser,
    run_parsed_args,
)
from earthground.cli.lcsc.cli import (
    configure_lcsc_parser,
    run_parsed_args as run_lcsc_args,
)
from earthground.cli.update_footprints import (
    configure_update_footprints_parser,
    run_parsed_args as run_update_footprints_args,
)
from earthground.cli.analysis_reports import (
    configure_straps_parser,
    configure_thermal_parser,
    run_straps_args,
    run_thermal_args,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="earthground",
        description="Tools for software-defined electrical design",
    )
    commands = parser.add_subparsers(dest="earthground_command", required=True)

    kicad = commands.add_parser("kicad", help="KiCad integration tools")
    kicad_commands = kicad.add_subparsers(dest="kicad_command", required=True)

    catalog = kicad_commands.add_parser(
        "catalog", help="Manage and query the KiCad footprint catalog"
    )
    configure_catalog_parser(catalog)

    update_footprints = kicad_commands.add_parser(
        "update-footprints",
        help="Update every PCB footprint from an Earthground design",
    )
    configure_update_footprints_parser(update_footprints)

    lcsc = commands.add_parser("lcsc", help="Query the LCSC component database")
    configure_lcsc_parser(lcsc)

    compile_command = commands.add_parser(
        "compile", help="Load and validate an Earthground design project"
    )
    configure_compile_parser(compile_command)

    straps = commands.add_parser(
        "straps", help="Resolve and report configuration strap pins"
    )
    configure_straps_parser(straps)

    thermal = commands.add_parser(
        "thermal", help="Generate a component thermal-analysis CSV"
    )
    configure_thermal_parser(thermal)

    export = commands.add_parser("export", help="Export an Earthground design project")
    export_commands = export.add_subparsers(dest="export_command", required=True)
    export_kicad = export_commands.add_parser(
        "kicad", help="Compile and export a Python design file as a KiCad board"
    )
    configure_kicad_export_parser(export_kicad)

    skills = commands.add_parser("skills", help="Manage Earthground agent skills")
    skills_commands = skills.add_subparsers(dest="skills_command", required=True)
    skills_commands.add_parser(
        "add",
        help="Add Earthground skills to this project's .claude directory",
        description=(
            "Confirm, then add Earthground skills to this project's .claude directory"
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.earthground_command == "compile":
        return run_compile_args(args)
    if args.earthground_command == "straps":
        return run_straps_args(args)
    if args.earthground_command == "thermal":
        return run_thermal_args(args)
    if args.earthground_command == "export":
        return run_kicad_export_args(args)
    if args.earthground_command == "skills":
        return run_skills_args(args)
    if args.earthground_command == "lcsc":
        return run_lcsc_args(args)
    if args.kicad_command == "update-footprints":
        return run_update_footprints_args(args)
    return run_parsed_args(args)


if __name__ == "__main__":
    raise SystemExit(main())
