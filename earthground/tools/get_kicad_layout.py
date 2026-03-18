#!/usr/bin/env python3
"""
Script to extract component layouts from a KiCad PCB file.

Converts footprints to Dict[str, layout.Placement] format compatible with
Layout.placement.
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


def _at_to_position(at) -> layout.Position:
    """Convert pykicad footprint/refdes .at to layout.Position."""
    if hasattr(at, "x") and hasattr(at, "y"):
        angle = getattr(at, "angle", 0.0) or 0.0
        return layout.Position(x=float(at.x), y=float(at.y), angle=float(angle))
    if isinstance(at, (list, tuple)):
        x = float(at[0])
        y = float(at[1])
        angle = float(at[2]) if len(at) > 2 else 0.0
        return layout.Position(x=x, y=y, angle=angle)
    raise TypeError(f"Cannot convert .at to Position: {type(at)}")


def extract_layouts(board_path: pathlib.Path) -> Dict[str, layout.Placement]:
    """
    Extract component placements from a KiCad PCB file.

    :param board_path: Path to the .kicad_pcb file
    :type board_path: pathlib.Path
    :return: Dictionary mapping refdes to Placement (position only; id=None)
    :rtype: Dict[str, layout.Placement]
    """
    logger.info(f"Loading board file: {board_path}")
    board = read_in_pcb_from_kicad_pcb(board_path)
    logger.info(f"Found {len(board.footprints)} footprints in board file")
    cid_mapper = {}

    placements = {}
    for i, footprint in enumerate(board.footprints):
        refdes_props = [p for p in footprint.properties if p.name == "Reference"]
        if not refdes_props:
            logger.warning(f"Footprint {i} has no reference designator")
            for prop in footprint.properties:
                logger.debug(f"  - property: {prop.name} = {prop.value}")
            continue
        refdes = refdes_props[0]
        prefix = refdes.value[0] if refdes.value else "?"
        cid_mapper[prefix] = cid_mapper.get(prefix, 0) + 1
        refdes_str = prefix + str(cid_mapper[prefix])
        position = _at_to_position(footprint.at)
        placements[refdes_str] = layout.Placement(position=position, id=None)
        logger.debug(f"Extracted placement for {refdes_str}: position={position}")

    logger.info(f"Extracted {len(placements)} placements")
    return placements


def print_layouts(placements: Dict[str, layout.Placement]):
    """Print placements in a readable format (layout.Placement)."""
    print("{")
    for refdes, pl in sorted(placements.items()):
        pos = pl.position
        id_str = f"layout.Orientation.{pl.id.name}" if pl.id is not None else "None"
        print(f'    "{refdes}": layout.Placement(')
        print(
            f"        position=layout.Position(x={pos.x}, y={pos.y}, angle={pos.angle}),"
        )
        if pl.id is not None:
            print(f"        id={id_str},")
        print("    ),")
    print("}")


def _position_diff(pos1: layout.Position, pos2: layout.Position) -> bool:
    return pos1.x != pos2.x or pos1.y != pos2.y or pos1.angle != pos2.angle


def diff_layout(
    path1: pathlib.Path,
    path2: pathlib.Path,
) -> bool:
    placements_1 = extract_layouts(path1)
    placements_2 = extract_layouts(path2)
    print("================================================")
    print("DIFFERENCES:")
    print(f"  - {path1}")
    print(f"  - {path2}")
    print("------------------------------------------------")
    found_diffs = False
    all_keys = set(placements_1.keys()) | set(placements_2.keys())
    for key in sorted(all_keys):
        p1 = placements_1.get(key)
        p2 = placements_2.get(key)
        if p1 is None:
            print(f"  - {key} added")
            found_diffs = True
        elif p2 is None:
            print(f"  - {key} removed")
            found_diffs = True
        elif p1.position != p2.position or p1.id != p2.id:
            if _position_diff(p1.position, p2.position):
                print(f"  - {key} position: {p1.position} -> {p2.position}")
                found_diffs = True
            if p1.id != p2.id:
                print(f"  - {key} id: {p1.id} -> {p2.id}")
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
            placements = extract_layouts(board_path)
            if placements:
                print_layouts(placements)
            else:
                logger.warning(
                    "No placements were extracted from the board file"
                )
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error processing file: {e}", exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
