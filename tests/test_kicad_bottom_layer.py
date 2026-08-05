import pykicad.models.pcb as pcb
from pykicad import FootprintBuilder

import earthground.components as cmp
import earthground.exporters.kicad as kicad
import earthground.footprints.passives as pfp
import earthground.layout as layout_lib
from earthground.importers.kicad import KicadFootprint
from earthground.library.integrated_circuits.voltage_regulators.linear.lm317 import (
    LM317AMDTX,
)
from earthground.schematic import Design


def _property(footprint: pcb.Footprint, name: str) -> pcb.Property:
    return next(item for item in footprint.property if item.name == name)


def _reference(footprint: pcb.Footprint) -> pcb.Property | pcb.FpText:
    reference = FootprintBuilder(footprint).reference
    assert reference is not None
    return reference


def _export_single_component(component: cmp.Component, placement: layout_lib.Placement):
    design = Design("TEST")
    design.add_component(component)
    cid = next(iter(design.components))
    component = design.components[cid]
    design.layout.placement[cid] = placement
    design.join_net(component.pins[1], "NET_A")
    if len(component.pins) > 1:
        design.join_net(component.pins[2], "NET_B")

    exporter = kicad.KicadExporter(design)
    exporter.convert_to_kicad(design)
    assert len(exporter.board.footprint) == 1
    return exporter.board.footprint[0]


def test_top_layer_placement_remains_default_and_backwards_compatible():
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)

    footprint = _export_single_component(
        component,
        layout_lib.Placement(
            position=layout_lib.Position(x=10, y=20, angle=90),
            id=None,
        ),
    )

    reference = _reference(footprint)
    assert footprint.layer == "F.Cu"
    assert footprint.at == pcb.Position(x=10, y=20, angle=-90)
    assert reference.layer == "F.SilkS"
    assert reference.effects.justify.mirror is False
    assert footprint.pads[0].layers == ["F.Cu", "F.Mask", "F.Paste"]


def test_bottom_layer_native_smd_footprint_uses_bottom_layers_and_mirrored_text():
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)

    footprint = _export_single_component(
        component,
        layout_lib.Placement(
            position=layout_lib.Position(x=10, y=20, angle=90),
            id=None,
            layer=layout_lib.Layer.BOTTOM,
        ),
    )

    reference = _reference(footprint)
    assert footprint.layer == "B.Cu"
    assert footprint.at == pcb.Position(x=10, y=20, angle=-90)
    assert reference.layer == "B.SilkS"
    assert reference.effects.justify.mirror is True
    assert footprint.pads[0].layers == ["B.Cu", "B.Mask", "B.Paste"]
    assert footprint.pads[1].layers == ["B.Cu", "B.Mask", "B.Paste"]


def test_bottom_layer_imported_footprint_switches_text_and_smd_pad_layers():
    component = cmp.Component("U")
    component.name = "ImportedAsymmetric"
    component.mpn = "IMP-123"
    component.manufacturer = "Imported Corp"
    component.pins = cmp.PinContainer.from_dict({1: "P1", 2: "P2"}, component)
    component.footprint = KicadFootprint(
        "Test",
        "ImportedAsymmetric",
        """
        (footprint "ImportedAsymmetric"
          (version 20240108)
          (generator "test")
          (layer "F.Cu")
          (fp_text reference "REF**" (at 0 1 0) (layer "F.SilkS")
            (effects (font (size 1 1) (thickness 0.15))))
          (fp_text value "ImportedAsymmetric" (at 0 -1 0) (layer "F.Fab")
            (effects (font (size 1 1) (thickness 0.15))))
          (fp_line (start 0 0) (end 2 0) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
          (pad "1" smd rect (at -1 1 15) (size 1.55 0.4) (layers "F.Cu" "F.Mask" "F.Paste"))
          (pad "2" smd rect (at 1 -2 -25) (size 2.75 6.2) (layers "F.Cu" "F.Mask" "F.Paste"))
        )
        """.strip(),
    )

    footprint = _export_single_component(
        component,
        layout_lib.Placement(
            position=layout_lib.Position(x=5, y=6, angle=180),
            id=None,
            layer=layout_lib.Layer.BOTTOM,
        ),
    )

    reference = _reference(footprint)
    value = next(item for item in footprint.fp_text if item.name == "value")
    assert footprint.layer == "B.Cu"
    assert footprint.at == pcb.Position(x=5, y=6, angle=-180)
    assert reference.layer == "B.SilkS"
    assert reference.effects.justify.mirror is True
    assert value.layer == "B.Fab"
    assert value.effects.justify.mirror is True
    assert value.at.x == 0
    assert value.at.y == -1
    assert footprint.pads[0].at == pcb.Position(x=1, y=1, angle=-195)
    assert footprint.pads[1].at == pcb.Position(x=-1, y=-2, angle=-155)
    assert footprint.pads[0].size == pcb.Size(width=1.55, height=0.4)
    assert footprint.pads[1].size == pcb.Size(width=2.75, height=6.2)
    assert footprint.pads[0].layers == ["B.Cu", "B.Mask", "B.Paste"]
    assert footprint.pads[1].layers == ["B.Cu", "B.Mask", "B.Paste"]
    assert _property(footprint, "MPN").value == "IMP-123"
    assert _property(footprint, "Manufacturer").value == "Imported Corp"


def test_module_placement_on_bottom_layer_pushes_child_footprints_to_bottom():
    design = LM317AMDTX.generate_design(3.3)
    design.add_module(LM317AMDTX.generate_design(3.3))
    design.layout.placement["REG1"] = layout_lib.Placement(
        position=layout_lib.Position(x=0.0, y=20.0, angle=0.0),
        layer=layout_lib.Layer.BOTTOM,
    )

    exporter = kicad.KicadExporter(design)
    exporter.convert_to_kicad(design)

    front_count = sum(
        1 for footprint in exporter.board.footprint if footprint.layer == "F.Cu"
    )
    back_count = sum(
        1 for footprint in exporter.board.footprint if footprint.layer == "B.Cu"
    )

    assert front_count == 5
    assert back_count == 5


def test_bottom_layer_module_child_reference_stays_local_to_the_footprint():
    design = LM317AMDTX.generate_design(3.3)
    design.add_module(LM317AMDTX.generate_design(3.3))
    design.layout.placement["REG1"] = layout_lib.Placement(
        position=layout_lib.Position(x=0.0, y=20.0, angle=0.0),
        layer=layout_lib.Layer.BOTTOM,
    )

    exporter = kicad.KicadExporter(design)
    exporter.convert_to_kicad(design)

    reg1_u1 = next(
        footprint
        for footprint in exporter.board.footprint
        if FootprintBuilder(footprint).reference is not None
        and FootprintBuilder(footprint).reference.value == "REG1_U1"
    )
    reference = _reference(reg1_u1)

    assert reg1_u1.at == pcb.Position(x=0.0, y=20.0, angle=-0.0)
    assert reference.at == pcb.Position(x=0.0, y=0.0, angle=0.0)


def test_bottom_layer_native_footprint_geometry_is_mirrored_across_y_axis():
    design = Design("T")
    component = design.add_component(LM317AMDTX())
    design.join_net(component.pins[1], "A")
    design.join_net(component.pins[2], "B")
    design.join_net(component.pins[3], "C")

    exporter = kicad.KicadExporter(design)
    top = exporter.parse_footprint(
        component.refdes,
        component,
        pcb.Position(x=0, y=0, angle=0),
        pcb.Position(x=0, y=-20, angle=0),
        design,
        layout_lib.Orientation.TOP,
        layout_lib.Layer.TOP,
    )
    bottom = exporter.parse_footprint(
        component.refdes,
        component,
        pcb.Position(x=0, y=0, angle=0),
        pcb.Position(x=0, y=-20, angle=0),
        design,
        layout_lib.Orientation.TOP,
        layout_lib.Layer.BOTTOM,
    )

    assert _reference(top).at == pcb.Position(x=0, y=-20, angle=0)
    assert _reference(bottom).at == pcb.Position(x=0, y=-20, angle=0)
    assert bottom.pads[0].at == pcb.Position(x=4.38, y=-2.285, angle=0)
    assert bottom.pads[1].at == pcb.Position(x=-2.285, y=0, angle=0)
    assert bottom.pads[2].at == pcb.Position(x=4.38, y=2.285, angle=0)


def test_rotated_180_left_reference_uses_left_side_local_offset():
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)

    footprint = _export_single_component(
        component,
        layout_lib.Placement(
            position=layout_lib.Position(x=10, y=20, angle=180),
            id=layout_lib.Orientation.LEFT,
        ),
    )

    reference = _reference(footprint)

    assert footprint.at == pcb.Position(x=10, y=20, angle=-180)
    assert reference.at.x > 0
    assert reference.at.y == 0
    assert reference.effects.justify.horizontal == "right"


def test_native_footprint_description_uses_component_mpn_when_available():
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)
    component.mpn = "RC0805FR-07100RL"
    component.manufacturer = "Yageo"

    footprint = _export_single_component(
        component,
        layout_lib.Placement(
            position=layout_lib.Position(x=10, y=20, angle=0),
            id=None,
        ),
    )

    assert footprint.description == "RC0805FR-07100RL"
    assert _property(footprint, "MPN").value == "RC0805FR-07100RL"
    assert _property(footprint, "Manufacturer").value == "Yageo"
