#!/usr/bin/env python3
"""
Script to extract component layouts from a KiCad PCB file.

Converts footprints to Dict[str, layout.ComponentLayout] format.
"""

import logging
import pathlib
import sys
from typing import Dict

from pykicad.parser.kicad_sexp import read_in_pcb_from_kicad_pcb

import earthground.layout as layout

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr
)
logger = logging.getLogger(__name__)


def extract_layouts(board_path: pathlib.Path) -> Dict[str, layout.ComponentLayout]:
    """
    Extract component layouts from a KiCad PCB file.

    :param board_path: Path to the .kicad_pcb file
    :type board_path: pathlib.Path
    :return: Dictionary mapping refdes to ComponentLayout
    :rtype: Dict[str, layout.ComponentLayout]
    """
    logger.info(f"Loading board file: {board_path}")
    board = read_in_pcb_from_kicad_pcb(board_path)
    logger.info(f"Found {len(board.footprints)} footprints in board file")
    cid_mapper = {}

    layouts = {}
    for i, footprint in enumerate(board.footprints):
        # Get reference designator
        refdes = [prop for prop in footprint.properties if prop.name == "Reference"][0]
        if not refdes:
            logger.warning(f"Footprint {i} has no reference designator")
            id_position = layout.Position(x=0.0, y=0.0, angle=0.0)
            for prop in footprint.properties:
                logger.debug(f"  - property: {prop.name} = {prop.value}")
            continue
        else:
            id_position = refdes.at
        prefix = refdes.value[0]
        cid_mapper[prefix] = cid_mapper.get(prefix, 0) + 1
        layouts[prefix + str(cid_mapper[prefix])] = layout.ComponentLayout(
            id=id_position, component=footprint.at
        )
        logger.debug(
            f"Extracted layout for {refdes}: component={footprint.at}, id={id_position}"
        )

    logger.info(f"Extracted {len(layouts)} component layouts")
    return layouts


def print_layouts(layouts: Dict[str, layout.ComponentLayout]):
    """Print layouts in a readable format."""
    print("{")
    for refdes, comp_layout in sorted(layouts.items()):
        print(f'    "{refdes}": layout_lib.ComponentLayout(')
        print(
            f"        id=layout_lib.Position(x={comp_layout.id.x}, y={comp_layout.id.y}, angle={comp_layout.id.angle}),"
        )
        print(
            f"        component=layout_lib.Position(x={comp_layout.component.x}, y={comp_layout.component.y}, angle={comp_layout.component.angle})"
        )
        print("    ),")
    print("}")


def compare_positions(pos1: layout.Position, pos2: layout.Position) -> bool:
    is_different = pos1.x != pos2.x or pos1.y != pos2.y or pos1.angle != pos2.angle
    return is_different


def diff_layout(
    path1: pathlib.Path,
    path2: pathlib.Path,
) -> bool:
    layout_1 = extract_layouts(path1)
    layout_2 = extract_layouts(path2)
    # Compare component layouts by their reference designators and report changes.
    print("================================================")
    print(f"DIFFERENCES: ")
    print(f"  - {path1}")
    print(f"  - {path2}")
    print("------------------------------------------------")
    found_diffs = False
    all_keys = set(layout_1.keys()) | set(layout_2.keys())
    for key in sorted(all_keys):
        c1 = layout_1.get(key)
        c2 = layout_2.get(key)
        if c1 is None:
            print(f"  - {key} added")
            found_diffs = True
        elif c2 is None:
            print(f"  - {key} removed")
            found_diffs = True
        if c1.id == c2.id and c1.component == c2.component:
            continue
        else:
            if compare_positions(c1.id, c2.id):
                print(f"  - {key} id changed: {c1.id} -> {c2.id}")
                found_diffs = True
            if compare_positions(c1.component, c2.component):
                print(f"  - {key} component changed: {c1.component} -> {c2.component}")
                found_diffs = True
    if not found_diffs:
        print("Both files are identical.")
    print("================================================")
    return found_diffs


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract component layouts from a KiCad PCB file or compare two files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "board_file",
        type=pathlib.Path,
        help="Path to the .kicad_pcb file (or old file if using --diff)",
    )
    parser.add_argument(
        "--diff",
        type=pathlib.Path,
        metavar="NEW_FILE",
        help="Compare two board files. OLD_FILE is the baseline, NEW_FILE is the modified version.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose/debug logging"
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational messages (only show warnings/errors)",
    )

    args = parser.parse_args()

    # Set logging level based on flags
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    # Handle diff mode
    if args.diff:
        old_path = args.board_file
        new_path = args.diff

        if not old_path.exists():
            logger.error(f"Old file not found: {old_path}")
            sys.exit(1)

        if not new_path.exists():
            logger.error(f"New file not found: {new_path}")
            sys.exit(1)

        diff_layout(old_path, new_path)
    else:
        # Single file extraction mode
        board_path = args.board_file
        if not board_path.exists():
            logger.error(f"File not found: {board_path}")
            sys.exit(1)

        if not board_path.suffix == ".kicad_pcb":
            logger.warning(f"File does not have .kicad_pcb extension: {board_path}")

        try:
            layouts = extract_layouts(board_path)
            if layouts:
                print_layouts(layouts)
            else:
                logger.warning(
                    "No component layouts were extracted from the board file"
                )
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error processing file: {e}", exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
