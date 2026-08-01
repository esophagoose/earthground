"""Update footprint definitions in an existing KiCad PCB file."""

from __future__ import annotations

import copy
import os
import pathlib
import stat
import sys
import tempfile
from typing import Optional, Sequence

from pykicad import FootprintBuilder, Pcb, PcbBuilder, read_from_file, write_to_string
import pykicad.models.pcb as pcb

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


def _reference_text(footprint: pcb.Footprint) -> pcb.Property | pcb.FpText | None:
    return FootprintBuilder(footprint).reference


def _footprint_refdes(footprint: pcb.Footprint) -> str:
    reference_text = _reference_text(footprint)
    if reference_text is not None and reference_text.value:
        return reference_text.value
    raise FootprintUpdateError("PCB footprint has no Reference property or text")


def _index_board_footprints(
    footprints: list[pcb.Footprint],
) -> dict[str, pcb.Footprint]:
    indexed = {}
    for footprint in footprints:
        refdes = _footprint_refdes(footprint)
        if refdes in indexed:
            raise FootprintUpdateError(f"PCB contains duplicate refdes: {refdes}")
        indexed[refdes] = footprint
    return indexed


def _board_net_names(board: Pcb) -> set[str]:
    names = {net.name for net in board.net}
    names.update(
        pad.net.name
        for footprint in board.footprint
        for pad in footprint.pads
        if pad.net is not None and pad.net.name is not None
    )
    return names


def _validate_component_match(
    design_components: dict[str, cmp.Component],
    pcb_footprints: dict[str, pcb.Footprint],
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
    old: pcb.Footprint,
    new: pcb.Footprint,
    refdes: str,
) -> None:
    new.at = copy.deepcopy(old.at)
    new.layer = old.layer
    new.tstamp = old.tstamp
    new.exclude_from_bom = old.exclude_from_bom
    new.exclude_from_pos_files = old.exclude_from_pos_files
    for name, value in (old.model_extra or {}).items():
        setattr(new, name, copy.deepcopy(value))

    properties = {item.name: copy.deepcopy(item) for item in old.property}
    properties.update({item.name: item for item in new.property})
    new.property = list(properties.values())

    old_reference = _reference_text(old)
    new_reference = _reference_text(new)
    if old_reference is not None:
        preserved_reference = copy.deepcopy(old_reference)
        preserved_reference.value = refdes
        if isinstance(new_reference, pcb.Property):
            new.property.remove(new_reference)
        elif isinstance(new_reference, pcb.FpText):
            new.fp_text.remove(new_reference)
        if isinstance(preserved_reference, pcb.Property):
            new.property.insert(0, preserved_reference)
        else:
            new.fp_text.insert(0, preserved_reference)

    old_pads = {pad.number: pad for pad in old.pads}
    for pad in new.pads:
        old_pad = old_pads.get(pad.number)
        if old_pad is not None:
            pad.tstamp = old_pad.tstamp
            for name, value in (old_pad.model_extra or {}).items():
                if name in {"uuid", "tstamp"}:
                    setattr(pad, name, copy.deepcopy(value))


def _replacement_footprint(
    exporter: kicad_exporter.KicadExporter,
    refdes: str,
    component: cmp.Component,
    old_footprint: pcb.Footprint,
) -> pcb.Footprint:
    if old_footprint.at is None:
        raise FootprintUpdateError(f"PCB footprint {refdes} has no position")

    design_position = pcb.Position(
        x=old_footprint.at.x,
        y=old_footprint.at.y,
        angle=-old_footprint.at.angle,
    )
    old_reference = _reference_text(old_footprint)
    reference_position = (
        copy.deepcopy(old_reference.at)
        if old_reference is not None and old_reference.at is not None
        else pcb.Position(x=0, y=0, angle=0)
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
    """Replace every PCB footprint from ``design`` using PyKiCad."""
    path = pathlib.Path(pcb_path).expanduser().resolve()
    if path.suffix != ".kicad_pcb":
        raise FootprintUpdateError(f"Expected a .kicad_pcb file: {path}")
    if not path.is_file():
        raise FootprintUpdateError(f"PCB file not found: {path}")

    try:
        board = read_from_file(path).model
        if not isinstance(board, Pcb):
            raise TypeError("document is not a KiCad PCB")
    except Exception as exc:
        raise FootprintUpdateError(f"Unable to parse KiCad PCB {path}: {exc}") from exc

    pcb_footprints = _index_board_footprints(board.footprint)
    design_components = _flatten_components(design)
    _validate_component_match(design_components, pcb_footprints)

    exporter = kicad_exporter.KicadExporter(design)
    exporter.builder = PcbBuilder(board)
    exporter.board = board
    original_net_names = _board_net_names(board)

    replacements = []
    for old_footprint in board.footprint:
        refdes = _footprint_refdes(old_footprint)
        replacement = _replacement_footprint(
            exporter,
            refdes,
            design_components[refdes],
            old_footprint,
        )
        replacements.append(replacement)

        replacement_net_names = {
            pad.net.name
            for pad in replacement.pads
            if pad.net is not None and pad.net.name is not None
        }
        added_nets = replacement_net_names - original_net_names
        if added_nets:
            raise FootprintUpdateError(
                f"Cannot update {refdes} without changing the PCB net table; "
                f"missing nets: {', '.join(sorted(added_nets))}"
            )

    board.footprint = replacements
    _write_atomically(path, write_to_string(board))
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
