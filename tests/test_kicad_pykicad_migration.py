import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from pykicad import Pcb, PcbBuilder, read_from_file, write_to_file
from pykicad.models.base import Point
import pykicad.models.pcb as pcb

import earthground.components as cmp
from earthground.exporters.kicad import KicadExporter
import earthground.footprints.passives as pfp
from earthground.importers.kicad import KicadFootprint
import earthground.layout as layout_lib
from earthground.schematic import Design
from earthground.tools.get_kicad_layout import extract_layouts


def _resistor_design(name: str = "MIGRATION") -> Design:
    design = Design(name)
    resistor = cmp.Resistor(100)
    resistor.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)
    design.add_component(resistor)
    cid = next(iter(design.components))
    resistor = design.components[cid]
    design.join_net(resistor.pins[1], "GND")
    design.join_net(resistor.pins[2], "VCC")
    design.layout.outline = layout_lib.BoundingBox(x1=0, y1=0, x2=20, y2=10)
    design.layout.placement[cid] = layout_lib.Placement(
        position=layout_lib.Position(x=5, y=5, angle=0)
    )
    return design


def _assert_kicad_accepts(path: Path, tmp_path: Path) -> None:
    executable = shutil.which("kicad-cli")
    if executable is None:
        pytest.skip("kicad-cli is not installed")
    result = subprocess.run(
        [executable, "pcb", "drc", "--output", str(tmp_path / "drc.rpt"), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _find_pcbnew_python() -> Path | None:
    candidates = [Path(sys.executable)]
    if sys.platform == "darwin":
        candidates.extend(
            Path("/Applications").glob(
                "KiCad*/KiCad.app/Contents/Frameworks/Python.framework/"
                "Versions/*/bin/python3"
            )
        )
    for executable in candidates:
        result = subprocess.run(
            [str(executable), "-c", "import pcbnew"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return executable
    return None


def test_generated_board_round_trips_and_opens_in_kicad_10(tmp_path: Path):
    design = _resistor_design()
    design.layout.pours.append(layout_lib.PourLayer(net_name="GND", layer=2))
    design.layout.vias.append(
        layout_lib.ViaConfig(
            location=layout_lib.Position(x=10, y=5, angle=0),
            net_name="GND",
            hole_size=0.8,
            drill_size=0.4,
        )
    )

    KicadExporter(design).save(tmp_path)
    output = tmp_path / "MIGRATION.kicad_pcb"
    board = read_from_file(output).model

    assert isinstance(board, Pcb)
    assert board.version == 20260206
    assert len(board.footprint) == 1
    assert board.footprint[0].pads[0].net.name == "GND"
    assert board.zone[0].net == "GND"
    assert board.track[0].net == "GND"
    assert extract_layouts(output)["R1"].position == layout_lib.Position(5, 5, 0)
    _assert_kicad_accepts(output, tmp_path)


def test_imported_footprint_preserves_unnumbered_pad_without_net(tmp_path: Path):
    component = cmp.Component("U")
    component.name = "QFN_WITH_EXPOSED_PAD"
    component.pins = cmp.PinContainer.from_dict({1: "P1", 2: "P2", 3: "EP"}, component)
    component.footprint = KicadFootprint(
        "Test",
        "QFN-2-1EP",
        """
        (footprint "QFN-2-1EP"
          (version 20240108)
          (generator "test")
          (layer "F.Cu")
          (pad "1" smd rect (at -1 0) (size 1 1)
            (layers "F.Cu" "F.Mask"))
          (pad "2" smd rect (at 1 0) (size 1 1)
            (layers "F.Cu" "F.Mask"))
          (pad "3" smd rect (at 0 0) (size 1.5 1.5)
            (layers "F.Cu" "F.Mask"))
          (pad "" smd rect (at 0 0) (size 0.6 0.6)
            (layers "F.Paste")))
        """.strip(),
    )
    assert list(component.footprint.pads) == ["1", "2", "3"]

    design = Design("UNNUMBERED_PAD")
    design.add_component(component)
    design.join_net(component.pins[1], "N1")
    design.join_net(component.pins[2], "N2")
    design.join_net(component.pins[3], "GND")
    design.layout.outline = layout_lib.BoundingBox(x1=0, y1=0, x2=10, y2=10)
    design.layout.placement["U1"] = layout_lib.Placement(
        position=layout_lib.Position(x=5, y=5, angle=0)
    )

    KicadExporter(design).save(tmp_path)
    board = read_from_file(tmp_path / "UNNUMBERED_PAD.kicad_pcb").model

    assert isinstance(board, Pcb)
    pads = board.footprint[0].pads
    assert [pad.number for pad in pads] == ["1", "2", "3", ""]
    assert [pad.net.name if pad.net else None for pad in pads] == [
        "N1",
        "N2",
        "GND",
        None,
    ]
    assert pads[-1].layers == ["F.Paste"]
    assert pads[-1].size == pcb.Size(width=0.6, height=0.6)


def test_kicad_loads_rotated_imported_pad_with_rotated_geometry(tmp_path: Path):
    pcbnew_python = _find_pcbnew_python()
    if pcbnew_python is None:
        pytest.skip("KiCad's pcbnew Python module is not installed")

    component = cmp.Component("U")
    component.name = "ROTATED_PAD"
    component.pins = cmp.PinContainer.from_dict({1: "P1"}, component)
    component.footprint = KicadFootprint(
        "Test",
        "ROTATED_PAD",
        """
        (footprint "ROTATED_PAD"
          (version 20240108)
          (generator "test")
          (layer "F.Cu")
          (pad "1" smd rect (at -2 0) (size 1.55 0.4)
            (layers "F.Cu" "F.Mask" "F.Paste")))
        """.strip(),
    )
    design = Design("ROTATED_PAD")
    design.add_component(component)
    design.layout.outline = layout_lib.BoundingBox(x1=0, y1=0, x2=20, y2=20)
    design.layout.placement["U1"] = layout_lib.Placement(
        position=layout_lib.Position(x=10, y=10, angle=90)
    )

    KicadExporter(design).save(tmp_path)
    output = tmp_path / "ROTATED_PAD.kicad_pcb"
    script = """
import json
import pcbnew
import sys

board = pcbnew.LoadBoard(sys.argv[1])
footprint = next(iter(board.GetFootprints()))
pad = next(iter(footprint.Pads()))
bounds = pad.GetBoundingBox()
print(json.dumps({
    "footprint_angle": footprint.GetOrientationDegrees(),
    "pad_angle": pad.GetOrientationDegrees(),
    "pad_width": pcbnew.ToMM(bounds.GetWidth()),
    "pad_height": pcbnew.ToMM(bounds.GetHeight()),
}))
"""
    result = subprocess.run(
        [str(pcbnew_python), "-c", script, str(output)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    geometry = json.loads(result.stdout)
    assert (geometry["pad_angle"] - geometry["footprint_angle"]) % 360 == 0
    assert geometry["pad_width"] == pytest.approx(0.4)
    assert geometry["pad_height"] == pytest.approx(1.55)


def test_existing_board_content_is_preserved_when_exporting(tmp_path: Path):
    source = PcbBuilder.create(generator="test").build()
    source.graphic_item.append(
        pcb.GraphicLine(
            start=Point(x=1, y=1),
            end=Point(x=2, y=2),
            stroke=pcb.Stroke(width=0.1, type="default"),
            layer="Dwgs.User",
        )
    )
    source_path = write_to_file(source, tmp_path / "source.kicad_pcb")
    design = _resistor_design("EXISTING")

    KicadExporter(design, pcb_path=source_path).save(tmp_path)
    output = tmp_path / "EXISTING.kicad_pcb"
    board = read_from_file(output).model

    assert isinstance(board, Pcb)
    assert len(board.footprint) == 1
    assert len(board.graphic_item) == 2
    assert board.graphic_item[0].layer == "Dwgs.User"
    _assert_kicad_accepts(output, tmp_path)


def test_four_layer_board_uses_modern_inner_layer_names():
    design = _resistor_design()
    design.layout.layer_count = 4

    exporter = KicadExporter(design)

    assert [layer.name for layer in exporter.builder.copper_layers] == [
        "F.Cu",
        "In1.Cu",
        "In2.Cu",
        "B.Cu",
    ]
    assert [layer.number for layer in exporter.board.layers[:4]] == [0, 4, 6, 2]


def test_imported_footprint_bbox_uses_pykicad_pad_geometry():
    footprint = KicadFootprint(
        "Test",
        "BBox",
        """
        (footprint "BBox"
          (version 20240108)
          (generator "test")
          (layer "F.Cu")
          (pad "1" smd rect (at -2 1) (size 2 4) (layers "F.Cu" "F.Mask"))
          (pad "2" smd rect (at 3 -1) (size 4 2) (layers "F.Cu" "F.Mask"))
        )
        """.strip(),
    )

    bbox = footprint.get_bbox()

    assert (bbox.x1, bbox.y1, bbox.x2, bbox.y2) == (-3, -2, 5, 3)
