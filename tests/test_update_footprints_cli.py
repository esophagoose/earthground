import pathlib

import pytest
from pykicad import Pcb, read_from_file, write_to_file

import earthground.components as cmp
import earthground.footprints.passives as passive_footprints
import earthground.layout as layout_lib
import earthground.schematic as sch_lib
from earthground.cli import main
from earthground.cli.update_footprints import (
    FootprintUpdateError,
    update_footprints,
)
from earthground.exporters.kicad import KicadExporter, get_index_fptext


def _board_without_footprints(path: pathlib.Path) -> Pcb:
    board = read_from_file(path).model
    assert isinstance(board, Pcb)
    board.footprint = []
    return board


def _make_design_and_board(path: pathlib.Path):
    design = sch_lib.Design("Footprint Update")
    resistor = cmp.Resistor("1k")
    resistor.footprint = passive_footprints.PassiveSmd(
        passive_footprints.PassivePackage.R0603
    )
    design.add_component(resistor)
    design.join_net(resistor.pins[1], "SIGNAL")
    design.join_net(resistor.pins[2], "GND")
    design.layout.placement["R1"] = layout_lib.Placement(
        position=layout_lib.Position(12.5, 9.25, -90),
        id=layout_lib.Orientation.TOP,
    )

    exporter = KicadExporter(design)
    exporter.convert_to_kicad(design)
    footprint = exporter.board.footprint[0]
    footprint.tstamp = "footprint-uuid"
    footprint.pads[0].tstamp = "pad-one-uuid"
    reference = get_index_fptext(footprint)
    assert reference is not None and reference.at is not None
    reference.at.x = 3.5
    reference.at.y = -2.25

    write_to_file(exporter.board, path)
    original = path.read_text(encoding="utf-8")
    original = original.replace(
        "\n)",
        '\n  (gr_text "DO NOT CHANGE" (at 1 2) (layer "F.SilkS") '
        "(effects (font (size 1 1))))\n)",
    )
    path.write_text(original, encoding="utf-8")

    resistor.footprint = passive_footprints.PassiveSmd(
        passive_footprints.PassivePackage.R0805
    )
    return design, original


def test_updates_all_footprints_without_changing_other_board_content(tmp_path):
    pcb_path = tmp_path / "board.kicad_pcb"
    design, _ = _make_design_and_board(pcb_path)
    original_board = _board_without_footprints(pcb_path)

    assert update_footprints(design, pcb_path) == 1

    assert _board_without_footprints(pcb_path) == original_board

    board = read_from_file(pcb_path).model
    assert isinstance(board, Pcb)
    footprint = board.footprint[0]
    reference = get_index_fptext(footprint)
    assert reference is not None and reference.at is not None
    pads = {pad.number: pad for pad in footprint.pads}

    assert footprint.name == "RES_1kΩ"
    assert footprint.at.x == 12.5
    assert footprint.at.y == 9.25
    assert footprint.at.angle == 90
    assert footprint.tstamp == "footprint-uuid"
    assert reference.value == "R1"
    assert reference.at.x == 3.5
    assert reference.at.y == -2.25
    assert pads["1"].size.width == 1.025
    assert pads["1"].size.height == 1.4
    assert pads["1"].net.name == "SIGNAL"
    assert pads["1"].tstamp == "pad-one-uuid"


def test_refdes_mismatch_fails_without_touching_the_file(tmp_path):
    pcb_path = tmp_path / "board.kicad_pcb"
    design, original = _make_design_and_board(pcb_path)
    mismatched = original.replace(
        'property "Reference" "R1"', 'property "Reference" "R9"'
    )
    pcb_path.write_text(mismatched, encoding="utf-8")

    with pytest.raises(FootprintUpdateError) as error:
        update_footprints(design, pcb_path)

    assert "missing from PCB: R1" in str(error.value)
    assert "unexpected in PCB: R9" in str(error.value)
    assert pcb_path.read_text(encoding="utf-8") == mismatched


def test_component_count_mismatch_fails_without_touching_the_file(tmp_path):
    pcb_path = tmp_path / "board.kicad_pcb"
    design, original = _make_design_and_board(pcb_path)
    capacitor = cmp.Capacitor("1u", "10")
    design.add_component(capacitor)

    with pytest.raises(FootprintUpdateError) as error:
        update_footprints(design, pcb_path)

    assert "design count=2" in str(error.value)
    assert "PCB count=1" in str(error.value)
    assert pcb_path.read_text(encoding="utf-8") == original


def test_hierarchical_cli_loads_design_script_and_updates_board(tmp_path, capsys):
    pcb_path = tmp_path / "board.kicad_pcb"
    _make_design_and_board(pcb_path)
    original_board = _board_without_footprints(pcb_path)
    script_path = tmp_path / "design.py"
    script_path.write_text(
        """
import earthground.components as cmp
import earthground.footprints.passives as footprints
import earthground.schematic as sch

design = sch.Design("Footprint Update")
resistor = cmp.Resistor("1k")
resistor.footprint = footprints.PassiveSmd(footprints.PassivePackage.R0805)
design.add_component(resistor)
design.join_net(resistor.pins[1], "SIGNAL")
design.join_net(resistor.pins[2], "GND")
""".lstrip(),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "kicad",
                "update-footprints",
                str(script_path),
                str(pcb_path),
            ]
        )
        == 0
    )

    output = capsys.readouterr()
    assert output.err == ""
    assert "Updated 1 footprints" in output.out
    assert _board_without_footprints(pcb_path) == original_board


def test_hierarchical_cli_reports_refdes_mismatch_and_leaves_file_unchanged(
    tmp_path, capsys
):
    pcb_path = tmp_path / "board.kicad_pcb"
    _, original = _make_design_and_board(pcb_path)
    mismatched = original.replace(
        'property "Reference" "R1"', 'property "Reference" "R9"'
    )
    pcb_path.write_text(mismatched, encoding="utf-8")
    script_path = tmp_path / "design.py"
    script_path.write_text(
        """
import earthground.components as cmp
import earthground.footprints.passives as footprints
import earthground.schematic as sch

design = sch.Design("Footprint Update")
resistor = cmp.Resistor("1k")
resistor.footprint = footprints.PassiveSmd(footprints.PassivePackage.R0805)
design.add_component(resistor)
""".lstrip(),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "kicad",
                "update-footprints",
                str(script_path),
                str(pcb_path),
            ]
        )
        == 1
    )

    output = capsys.readouterr()
    assert output.out == ""
    assert "missing from PCB: R1" in output.err
    assert "unexpected in PCB: R9" in output.err
    assert pcb_path.read_text(encoding="utf-8") == mismatched
