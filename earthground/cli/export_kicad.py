"""Export an Earthground Python design file to a KiCad board."""

from __future__ import annotations

import pathlib
import sys
from typing import Optional, Sequence

from earthground.exporters.kicad import KicadExporter
from earthground.schematic import SchematicValidationError
from earthground.cli.compile_project import (
    CompileProjectError,
    compile_design_file,
)

OUTPUT_DIRECTORY = "generated_outputs"


def export_kicad_project(design_file: pathlib.Path | str) -> pathlib.Path:
    """Compile a Python design file and export it as a KiCad PCB."""
    loaded = compile_design_file(design_file, initialize_config=True)
    design = loaded.design

    output_directory = loaded.project_root / OUTPUT_DIRECTORY
    output_path = output_directory / f"{design.name}.kicad_pcb"
    output_directory.mkdir(parents=True, exist_ok=True)

    exporter = KicadExporter(design)
    exporter.save(
        output_folder=output_directory,
        overwrite=output_path.exists(),
    )
    return output_path


def configure_kicad_export_parser(parser) -> None:
    """Add KiCad design-file export arguments to an argparse parser."""
    parser.add_argument(
        "design_file",
        help="Python file containing an Earthground design",
    )


def run_parsed_args(args) -> int:
    """Run the KiCad export command for already-parsed CLI arguments."""
    try:
        export_kicad_project(args.design_file)
    except CompileProjectError as exc:
        print(f"earthground export kicad: error: {exc}", file=sys.stderr)
        return 2
    except SchematicValidationError as exc:
        print(f"Export failed validation for {exc.design_name}:", file=sys.stderr)
        for error in exc.errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"KiCad export failed: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run KiCad project export as a standalone command."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="earthground export kicad",
        description="Compile and export an Earthground Python design file to KiCad",
    )
    configure_kicad_export_parser(parser)
    return run_parsed_args(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
