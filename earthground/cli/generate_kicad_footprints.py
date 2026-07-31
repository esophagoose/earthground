"""Generate autocompletable enums for the current project's KiCad footprints."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Optional, Sequence

from earthground.kicad.catalog import (
    ENVIRONMENT_OUTPUT,
    KicadCatalogError,
    catalog_is_fresh,
    find_footprint_path,
    generate_catalog,
    read_footprint_description,
    resolve_context,
    resolve_footprint_roots,
    scan_footprints,
)


def _add_project_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Earthground project root (defaults to upward discovery)",
    )
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        help="Config file path (defaults to .earthground/config.yaml)",
    )
    parser.add_argument(
        "--kicad-executable",
        type=pathlib.Path,
        help="Override the configured kicad-cli executable",
    )


def _add_catalog_options(parser: argparse.ArgumentParser) -> None:
    _add_project_options(parser)
    parser.add_argument(
        "--footprint-root",
        action="append",
        type=pathlib.Path,
        default=[],
        help="Additional footprint root; may be repeated",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=f"'{ENVIRONMENT_OUTPUT}' or a standalone .py path",
    )


def configure_catalog_parser(parser: argparse.ArgumentParser) -> None:
    """Add catalog actions to either the legacy or hierarchical CLI parser."""
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate",
        help="Create project config if needed, then generate the enum catalog",
    )
    generate_parser.set_defaults(catalog_handler=_run_generate)
    _add_catalog_options(generate_parser)
    generate_parser.add_argument(
        "--force", action="store_true", help="Regenerate even when current"
    )

    status_parser = subparsers.add_parser(
        "status", help="Show discovery and catalog freshness without writing"
    )
    status_parser.set_defaults(catalog_handler=_run_status)
    _add_catalog_options(status_parser)

    get_parser = subparsers.add_parser(
        "get", help="List installed footprints or get one footprint's details"
    )
    get_parser.set_defaults(catalog_handler=_run_get)
    _add_project_options(get_parser)
    get_parser.add_argument(
        "--footprint-root",
        action="append",
        type=pathlib.Path,
        default=[],
        help="Additional footprint root; may be repeated",
    )
    get_parser.add_argument(
        "--json",
        action="store_true",
        help="Return machine-readable JSON",
    )
    get_parser.add_argument(
        "library_or_reference",
        nargs="?",
        help="Optional library or Library:Footprint reference",
    )
    get_parser.add_argument(
        "footprint",
        nargs="?",
        help="Footprint name when the library is supplied separately",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="earthground kicad catalog",
        description="Manage Earthground's autocompletable KiCad footprint catalog",
    )
    configure_catalog_parser(parser)
    return parser


def _context_from_args(args: argparse.Namespace, initialize: bool):
    return resolve_context(
        project_root=args.project_root,
        config_path=args.config,
        executable=args.kicad_executable,
        footprint_roots=args.footprint_root,
        output=args.output,
        initialize=initialize,
    )


def _print_context(context, fresh: Optional[bool] = None) -> None:
    print(f"Project: {context.project.root}")
    print(f"Config: {context.project.config}")
    print(f"KiCad version: {context.installation.version}")
    print(f"Catalog output: {context.output}")
    print(f"Footprints: {len(context.entries)}")
    for root in context.roots:
        print(f"Footprint root: {root}")
    if fresh is not None:
        print(f"Catalog status: {'current' if fresh else 'missing or stale'}")


def _run_generate(args: argparse.Namespace) -> int:
    context = _context_from_args(args, initialize=True)
    changed = generate_catalog(context, force=args.force)
    _print_context(context, fresh=True)
    print("Catalog generated." if changed else "Catalog already current.")
    return 0


def _run_status(args: argparse.Namespace) -> int:
    context = _context_from_args(args, initialize=False)
    fresh = catalog_is_fresh(context)
    _print_context(context, fresh=fresh)
    return 0 if fresh else 1


def _parse_footprint_reference(
    library_or_reference: str, footprint: Optional[str]
) -> tuple[str, str]:
    if footprint is not None:
        library = library_or_reference
        footprint_name = footprint
    elif ":" in library_or_reference:
        library, footprint_name = library_or_reference.split(":", 1)
    else:
        raise KicadCatalogError(
            "A footprint must be written as 'Library:Footprint' or supplied as "
            "separate LIBRARY FOOTPRINT arguments."
        )
    library = library.removesuffix(".pretty")
    footprint_name = footprint_name.removesuffix(".kicad_mod")
    if not library or not footprint_name:
        raise KicadCatalogError("Both the library and footprint name are required.")
    return library, footprint_name


def _run_get(args: argparse.Namespace) -> int:
    roots = resolve_footprint_roots(
        additional_roots=args.footprint_root,
        project_root=args.project_root,
        config_path=args.config,
        executable=args.kicad_executable,
        initialize=False,
    )
    if args.library_or_reference is None:
        return _print_footprint_listing(roots, None, args.json)

    if args.footprint is None and ":" not in args.library_or_reference:
        return _print_footprint_listing(
            roots, args.library_or_reference.removesuffix(".pretty"), args.json
        )

    library, footprint_name = _parse_footprint_reference(
        args.library_or_reference, args.footprint
    )
    path = find_footprint_path(roots, library, footprint_name)
    description = read_footprint_description(path)
    result = {
        "reference": f"{library}:{footprint_name}",
        "library": library,
        "footprint": footprint_name,
        "description": description,
        "path": str(path),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Reference: {result['reference']}")
        print(f"Description: {description or '(none provided)'}")
        print(f"Path: {path}")
    return 0


def _print_footprint_listing(
    roots: Sequence[pathlib.Path], selected_library: Optional[str], as_json: bool
) -> int:
    entries = scan_footprints(roots)
    libraries: dict[str, list[dict[str, Optional[str]]]] = {}
    for entry in entries:
        if selected_library is None or entry.library == selected_library:
            path = entry.path or find_footprint_path(
                roots, entry.library, entry.footprint_name
            )
            libraries.setdefault(entry.library, []).append(
                {
                    "name": entry.footprint_name,
                    "description": read_footprint_description(path),
                }
            )

    if selected_library is not None and selected_library not in libraries:
        raise KicadCatalogError(
            f"Footprint library '{selected_library}' was not found."
        )

    footprint_count = sum(len(footprints) for footprints in libraries.values())
    if as_json:
        print(
            json.dumps(
                {
                    "library_count": len(libraries),
                    "footprint_count": footprint_count,
                    "libraries": libraries,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for library, footprints in libraries.items():
            print(f"{library}:")
            for footprint in footprints:
                print(f"  {footprint['name']}")
                print(
                    "    Description: "
                    f"{footprint['description'] or '(none provided)'}"
                )
        print(f"\nLibraries: {len(libraries)}")
        print(f"Footprints: {footprint_count}")
    return 0


def run_parsed_args(args: argparse.Namespace) -> int:
    try:
        return args.catalog_handler(args)
    except KicadCatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_parsed_args(args)


if __name__ == "__main__":
    raise SystemExit(main())
