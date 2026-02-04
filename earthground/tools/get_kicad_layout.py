#!/usr/bin/env python3
"""
Script to extract component layouts from a KiCad PCB file.

Converts footprints to Dict[str, layout.ComponentLayout] format.
"""

import logging
import pathlib
import pprint
import sys
from typing import Dict, Optional, Tuple

import kiutils.board
import kiutils.footprint as fp
import kiutils.items.common as base
from pykicad.parser.kicad_sexp import read_in_pcb_from_kicad_pcb

from earthground.tools import layout

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr
)
logger = logging.getLogger(__name__)


def get_reference_text(footprint: fp.Footprint) -> fp.FpText | None:
    """Get the reference text (ID) from a footprint."""
    for item in footprint.graphicItems:
        if isinstance(item, fp.FpText) and (
            item.type == "reference" or item.text == "${REFERENCE}"
        ):
            return item
    return None


def kiutil_to_layout_position(pos: base.Position) -> layout.Position:
    """Convert kiutils Position to layout.Position."""
    return layout.Position(
        x=float(pos.X),
        y=float(pos.Y),
        angle=float(pos.angle) if pos.angle is not None else 0.0,
    )


def get_reference_designator(footprint: fp.Footprint) -> str | None:
    """Get the reference designator from a footprint using multiple methods."""
    # Method 1: Check for reference in FpText items first (most reliable)
    for item in footprint.graphicItems:
        if isinstance(item, fp.FpText) and (
            item.type == "reference" or getattr(item, "text", None) == "${REFERENCE}"
        ):
            if item.text and item.text != "${REFERENCE}":
                return item.text

    # Method 2: Check properties dictionary
    if hasattr(footprint, "properties"):
        if isinstance(footprint.properties, dict):
            refdes = footprint.properties.get("Reference", None)
            if refdes:
                return refdes
        elif hasattr(footprint.properties, "get"):
            refdes = footprint.properties.get("Reference", None)
            if refdes:
                return refdes

    # Method 3: Check if there's a direct reference attribute
    if hasattr(footprint, "reference") and footprint.reference:
        return footprint.reference

    # Method 4: Check properties list (kiutils might use a list of Property objects)
    if hasattr(footprint, "properties") and isinstance(footprint.properties, list):
        for prop in footprint.properties:
            if hasattr(prop, "name") and prop.name == "Reference":
                if hasattr(prop, "value"):
                    return prop.value
                if hasattr(prop, "text"):
                    return prop.text

    return None


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

        layouts[refdes.value] = layout.ComponentLayout(
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
        print(f'    "{refdes}": ComponentLayout(')
        print(
            f"        id=Position(x={comp_layout.id.x}, y={comp_layout.id.y}, angle={comp_layout.id.angle}),"
        )
        print(
            f"        component=Position(x={comp_layout.component.x}, y={comp_layout.component.y}, angle={comp_layout.component.angle})"
        )
        print("    ),")
    print("}")


def _extract_footprints_for_diff(
    path: pathlib.Path,
) -> Dict[str, Dict[str, Optional[Tuple[float, float, float]]]]:
    """
    Extract footprints from a KiCad PCB file in the format needed for diff comparison.

    :param path: Path to the .kicad_pcb file
    :return: Dictionary mapping refdes to {"at": (x, y, angle), "ref_at": (x, y, angle)}
    """
    board = kiutils.board.Board.from_file(path)
    footprints = {}

    logger.debug(f"Found {len(board.footprints)} footprints in {path}")

    for footprint in board.footprints:
        ref = get_reference_designator(footprint)
        if not ref:
            logger.warning(f"Skipping footprint with no reference designator")
            continue

        # Get footprint position (component position)
        at = None
        if hasattr(footprint, "position") and footprint.position:
            pos = footprint.position
            angle = float(pos.angle) if pos.angle is not None else 0.0
            at = (float(pos.X), float(pos.Y), angle)

        # Get reference text position (ID position)
        ref_at = None
        ref_text = get_reference_text(footprint)
        if ref_text and hasattr(ref_text, "position"):
            pos = ref_text.position
            angle = float(pos.angle) if pos.angle is not None else 0.0
            ref_at = (float(pos.X), float(pos.Y), angle)

        footprints[ref] = {"at": at, "ref_at": ref_at}
        logger.debug(f"Extracted {ref}: at={at}, ref_at={ref_at}")

    logger.info(f"Extracted {len(footprints)} footprints from {path}")
    return footprints


def diff_layout(old_path: pathlib.Path, new_path: pathlib.Path) -> Dict[str, Dict]:
    """
    Compare two KiCad board files and return differences in footprint positions.

    :param old_path: Path to the baseline .kicad_pcb file
    :param new_path: Path to the modified .kicad_pcb file
    :return: Dictionary of differences, keyed by reference designator
    """
    logger.info(f"Comparing {old_path} (old) vs {new_path} (new)")
    old = _extract_footprints_for_diff(old_path)
    new = _extract_footprints_for_diff(new_path)

    refs = sorted(set(old.keys()) | set(new.keys()))
    diffs = {}

    for ref in refs:
        o = old.get(ref)
        n = new.get(ref)

        if o is None:
            logger.debug(f"{ref}: missing in old file, present in new")
            diffs[ref] = {"missing": "old", "at": n["at"], "ref_at": n["ref_at"]}
            continue

        if n is None:
            logger.debug(f"{ref}: missing in new file, present in old")
            diffs[ref] = {"missing": "new", "at": o["at"], "ref_at": o["ref_at"]}
            continue

        entry = {}
        # Compare positions (handle None values)
        if o["at"] != n["at"]:
            entry["at"] = n["at"]
            logger.debug(f"{ref}: position changed from {o['at']} to {n['at']}")

        if o["ref_at"] != n["ref_at"]:
            entry["ref_at"] = n["ref_at"]
            logger.debug(
                f"{ref}: reference text position changed from {o['ref_at']} to {n['ref_at']}"
            )

        if entry:
            diffs[ref] = entry

    logger.info(f"Found {len(diffs)} differences")
    return diffs


def print_diff(diffs: Dict[str, Dict], indent: int = 4):
    """Print diff results in a readable format."""
    print(pprint.pformat(diffs, sort_dicts=True, indent=indent))


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

        if not old_path.suffix == ".kicad_pcb":
            logger.warning(f"Old file does not have .kicad_pcb extension: {old_path}")

        if not new_path.suffix == ".kicad_pcb":
            logger.warning(f"New file does not have .kicad_pcb extension: {new_path}")

        try:
            diffs = diff_layout(old_path, new_path)
            print_diff(diffs)
        except Exception as e:
            logger.error(f"Error processing files: {e}", exc_info=True)
            sys.exit(1)
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
