"""Update footprint definitions in an existing KiCad PCB file."""

from __future__ import annotations

import copy
import os
import pathlib
import stat
import sys
import tempfile
from typing import Optional, Sequence

import kiutils.board as kicad_board
import kiutils.footprint as kicad_footprint
import kiutils.items.common as kicad_common

import earthground.components as cmp
import earthground.exporters.kicad as kicad_exporter
import earthground.layout as layout_lib
import earthground.schematic as sch_lib
from earthground.cli.compile_project import (
    CompileProjectError,
    compile_design_file,
)


class FootprintUpdateError(RuntimeError):
    """Raised when a PCB cannot be safely updated from a design."""


def _flatten_components(design: sch_lib.Design) -> dict[str, cmp.Component]:
    flattened = {}

    def walk(current_design: sch_lib.Design, prefix: str = "") -> None:
        for cid, component in current_design.components.items():
            refdes = f"{prefix}{cid}"
            if isinstance(component, cmp.ModuleComponent):
                walk(component.parent, prefix=f"{refdes}_")
            elif not component.virtual:
                if refdes in flattened:
                    raise FootprintUpdateError(
                        f"Earthground design contains duplicate refdes: {refdes}"
                    )
                flattened[refdes] = component

    walk(design)
    return flattened


def _reference_text(
    footprint: kicad_footprint.Footprint,
) -> kicad_footprint.FpText | None:
    return next(
        (
            item
            for item in footprint.graphicItems
            if isinstance(item, kicad_footprint.FpText) and item.type == "reference"
        ),
        None,
    )


def _footprint_refdes(footprint: kicad_footprint.Footprint) -> str:
    reference_property = footprint.properties.get("Reference")
    if reference_property:
        return str(reference_property)
    reference_text = _reference_text(footprint)
    if reference_text is not None and reference_text.text:
        return reference_text.text
    raise FootprintUpdateError("PCB footprint has no Reference property or text")


def _index_board_footprints(
    footprints: list[kicad_footprint.Footprint],
) -> dict[str, kicad_footprint.Footprint]:
    indexed = {}
    for footprint in footprints:
        refdes = _footprint_refdes(footprint)
        if refdes in indexed:
            raise FootprintUpdateError(f"PCB contains duplicate refdes: {refdes}")
        indexed[refdes] = footprint
    return indexed


def _validate_component_match(
    design_components: dict[str, cmp.Component],
    pcb_footprints: dict[str, kicad_footprint.Footprint],
) -> None:
    design_refdes = set(design_components)
    pcb_refdes = set(pcb_footprints)
    if len(design_components) == len(pcb_footprints) and design_refdes == pcb_refdes:
        return

    details = [
        "Earthground design and PCB components do not match",
        f"design count={len(design_components)}",
        f"PCB count={len(pcb_footprints)}",
    ]
    missing = sorted(design_refdes - pcb_refdes)
    unexpected = sorted(pcb_refdes - design_refdes)
    if missing:
        details.append(f"missing from PCB: {', '.join(missing)}")
    if unexpected:
        details.append(f"unexpected in PCB: {', '.join(unexpected)}")
    raise FootprintUpdateError("; ".join(details))


def _preserve_board_footprint_state(
    old: kicad_footprint.Footprint,
    new: kicad_footprint.Footprint,
    refdes: str,
) -> None:
    new.position = copy.deepcopy(old.position)
    new.layer = old.layer
    new.tstamp = old.tstamp
    new.path = old.path
    new.locked = old.locked
    new.placed = old.placed
    new.properties = {**old.properties, **new.properties}
    for attribute in (
        "boardOnly",
        "excludeFromPosFiles",
        "excludeFromBom",
        "allowMissingCourtyard",
    ):
        setattr(new.attributes, attribute, getattr(old.attributes, attribute))

    old_reference = _reference_text(old)
    new_reference = _reference_text(new)
    if old_reference is not None:
        preserved_reference = copy.deepcopy(old_reference)
        preserved_reference.text = refdes
        if new_reference is None:
            new.graphicItems.insert(0, preserved_reference)
        else:
            new.graphicItems[new.graphicItems.index(new_reference)] = (
                preserved_reference
            )

    old_pads = {pad.number: pad for pad in old.pads}
    for pad in new.pads:
        old_pad = old_pads.get(pad.number)
        if old_pad is not None:
            pad.tstamp = old_pad.tstamp


def _replacement_footprint(
    exporter: kicad_exporter.KicadExporter,
    refdes: str,
    component: cmp.Component,
    old_footprint: kicad_footprint.Footprint,
) -> kicad_footprint.Footprint:
    if old_footprint.position is None:
        raise FootprintUpdateError(f"PCB footprint {refdes} has no position")

    design_position = kicad_common.Position(
        X=old_footprint.position.X,
        Y=old_footprint.position.Y,
        angle=-(old_footprint.position.angle or 0),
    )
    old_reference = _reference_text(old_footprint)
    reference_position = (
        copy.deepcopy(old_reference.position)
        if old_reference is not None
        else kicad_common.Position(X=0, Y=0, angle=0)
    )
    layer = (
        layout_lib.Layer.BOTTOM
        if old_footprint.layer.startswith("B.")
        else layout_lib.Layer.TOP
    )
    new_footprint = exporter.parse_footprint(
        refdes,
        component,
        component_position=design_position,
        id_position=reference_position,
        schematic=component.parent,
        layer=layer,
    )
    _preserve_board_footprint_state(old_footprint, new_footprint, refdes)
    return new_footprint


def _write_atomically(path: pathlib.Path, content: str) -> None:
    source_mode = stat.S_IMODE(path.stat().st_mode)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temp_path = pathlib.Path(output.name)
            output.write(content)
        os.chmod(temp_path, source_mode)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def update_footprints(design: sch_lib.Design, pcb_path: str | pathlib.Path) -> int:
    """Replace every PCB footprint from ``design`` using kiutils."""
    path = pathlib.Path(pcb_path).expanduser().resolve()
    if path.suffix != ".kicad_pcb":
        raise FootprintUpdateError(f"Expected a .kicad_pcb file: {path}")
    if not path.is_file():
        raise FootprintUpdateError(f"PCB file not found: {path}")

    try:
        board = kicad_board.Board.from_file(path, encoding="utf-8")
    except Exception as exc:
        raise FootprintUpdateError(f"Unable to parse KiCad PCB {path}: {exc}") from exc

    pcb_footprints = _index_board_footprints(board.footprints)
    design_components = _flatten_components(design)
    _validate_component_match(design_components, pcb_footprints)

    exporter = kicad_exporter.KicadExporter(design)
    exporter.board.nets = list(board.nets)
    exporter._added_nets = {net.name: net for net in board.nets}
    original_net_names = set(exporter._added_nets)

    replacements = []
    for old_footprint in board.footprints:
        refdes = _footprint_refdes(old_footprint)
        replacements.append(
            _replacement_footprint(
                exporter,
                refdes,
                design_components[refdes],
                old_footprint,
            )
        )

        added_nets = set(exporter._added_nets) - original_net_names
        if added_nets:
            raise FootprintUpdateError(
                f"Cannot update {refdes} without changing the PCB net table; "
                f"missing nets: {', '.join(sorted(added_nets))}"
            )

    board.footprints = replacements
    _write_atomically(path, board.to_sexpr())
    return len(replacements)


def configure_update_footprints_parser(parser) -> None:
    """Add footprint update arguments to an argparse parser."""
    parser.add_argument(
        "design_file",
        help="Python file containing an Earthground design",
    )
    parser.add_argument(
        "pcb_file",
        help="Existing .kicad_pcb file to update in place",
    )


def run_parsed_args(args) -> int:
    """Run the footprint update command for already-parsed CLI arguments."""
    try:
        loaded = compile_design_file(args.design_file)
        count = update_footprints(loaded.design, args.pcb_file)
    except CompileProjectError as exc:
        print(f"earthground kicad update-footprints: error: {exc}", file=sys.stderr)
        return 2
    except sch_lib.SchematicValidationError as exc:
        print(f"Update failed validation for {exc.design_name}:", file=sys.stderr)
        for error in exc.errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    except FootprintUpdateError as exc:
        print(f"earthground kicad update-footprints: error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Footprint update failed: {exc}", file=sys.stderr)
        return 1

    print(f"Updated {count} footprints in {pathlib.Path(args.pcb_file)}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run footprint update as a standalone command."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="earthground kicad update-footprints",
        description="Update PCB footprints from an Earthground design",
    )
    configure_update_footprints_parser(parser)
    return run_parsed_args(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
