import pytest
from pykicad import FootprintBuilder
from pykicad.models.base import Point
import pykicad.models.pcb as pcb

import earthground.components as cmp
import earthground.exporters.kicad as kicad
import earthground.footprints.passives as pfp
import earthground.layout as layout_lib
from earthground.importers.kicad import KicadFootprint
from earthground.schematic import Design


def _property(footprint: pcb.Footprint, name: str) -> pcb.Property:
    return next(item for item in footprint.property if item.name == name)


def _text_items(footprint: pcb.Footprint) -> list[pcb.Property | pcb.FpText]:
    return list(FootprintBuilder(footprint).iter_text())


def _is_hidden(item: pcb.Property | pcb.FpText) -> bool:
    if isinstance(item, pcb.Property):
        return bool(item.hide)
    return bool(item.effects and item.effects.hide)


def test_parse_footprint():
    design = Design("TEST")
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)
    design.add_component(component)
    design.join_net(component.pins[1], "NET_A")
    design.join_net(component.pins[2], "NET_B")
    footprint = kicad.KicadExporter(design).parse_footprint(design, component)

    assert isinstance(footprint, pcb.Footprint)
    assert footprint.name == "RES_100Ω"
    assert _property(footprint, "MPN").value == ""
    assert _property(footprint, "Lifecycle").value == "Unknown"
    assert footprint.pads[0].number == "1"
    assert footprint.pads[0].net.name == "NET_A"
    assert footprint.pads[1].net.name == "NET_B"


def test_strict_export_rejects_fallback_placement():
    design = Design("STRICT")
    design.add_component(cmp.Resistor("1k"))

    with pytest.raises(ValueError, match="explicit placement for: R1"):
        kicad.KicadExporter(design, strict_placement=True).convert_to_kicad(design)

    design.layout.placement["R1"] = layout_lib.Placement.identity()
    kicad.KicadExporter(design, strict_placement=True).convert_to_kicad(design)


def test_parse_footprint_exports_provenance_and_distributor_metadata():
    design = Design("TEST")
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)
    component.datasheet = "https://example.test/resistor.pdf"
    component.datasheet_revision = "Rev C"
    component.datasheet_sha256 = "abc123"
    component.lifecycle = cmp.Lifecycle.ACTIVE
    component.distributor_ids["lcsc"] = "C123"
    design.add_component(component)

    footprint = kicad.KicadExporter(design).parse_footprint(design, component)

    assert _property(footprint, "Datasheet").value == component.datasheet
    assert _property(footprint, "Datasheet Revision").value == "Rev C"
    assert _property(footprint, "Datasheet SHA256").value == "abc123"
    assert _property(footprint, "Lifecycle").value == "Active"
    assert _property(footprint, "Distributor:lcsc").value == "C123"


def test_parse_footprint_can_skip_silkscreen_text():
    design = Design("TEST")
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)
    design.add_component(component)

    footprint = kicad.KicadExporter(design).parse_footprint(
        design,
        component,
        add_silkscreen_text=False,
    )

    text_items = _text_items(footprint)
    silk_text = [item for item in text_items if item.layer.endswith(".SilkS")]
    fab_text = [item for item in text_items if item.layer.endswith(".Fab")]
    assert silk_text
    assert all(_is_hidden(item) for item in silk_text)
    assert any(not _is_hidden(item) for item in fab_text)


def test_hidden_imported_reference_text_still_gets_component_refdes():
    design = Design("TEST")
    component = cmp.Component("U")
    component.name = "Imported"
    component.footprint = KicadFootprint(
        "Test",
        "Imported",
        """
        (footprint "Imported"
          (version 20240108)
          (generator "test")
          (layer "F.Cu")
          (fp_text reference "REF**" (at 0 1 0) (layer "F.SilkS")
            (effects (font (size 1 1) (thickness 0.15))))
          (fp_text value "Imported" (at 0 -1 0) (layer "F.Fab")
            (effects (font (size 1 1) (thickness 0.15))))
        )
        """.strip(),
    )
    design.add_component(component)

    footprint = kicad.KicadExporter(design).parse_footprint(
        "U99",
        component,
        schematic=design,
        add_silkscreen_text=False,
    )
    reference = kicad.get_index_fptext(footprint)

    assert reference.value == "U99"
    assert reference.layer == "F.SilkS"
    assert _is_hidden(reference)


def test_parse_footprint_can_skip_fab_text():
    design = Design("TEST")
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)
    design.add_component(component)

    footprint = kicad.KicadExporter(design).parse_footprint(
        design,
        component,
        add_fab_text=False,
    )

    text_items = _text_items(footprint)
    silk_text = [item for item in text_items if item.layer.endswith(".SilkS")]
    fab_text = [item for item in text_items if item.layer.endswith(".Fab")]
    assert any(not _is_hidden(item) for item in silk_text)
    assert fab_text
    assert all(_is_hidden(item) for item in fab_text)


def test_exporter_text_flags_apply_to_converted_footprints():
    design = Design("TEST")
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)
    design.add_component(component)

    exporter = kicad.KicadExporter(
        design,
        add_silkscreen_text=False,
        add_fab_text=False,
    )
    exporter.convert_to_kicad(design)

    text_items = [
        item
        for footprint in exporter.board.footprint
        for item in _text_items(footprint)
    ]
    assert all(
        _is_hidden(item)
        for item in text_items
        if item.layer.endswith((".SilkS", ".Fab"))
    )


def test_draw_fab_lines_adds_board_graphics_on_fab_layer():
    design = Design("TEST")
    design.layout.fab.append(
        layout_lib.FabLine(
            start=layout_lib.Position(x=1, y=2, angle=0),
            end=layout_lib.Position(x=3, y=4, angle=0),
        )
    )

    exporter = kicad.KicadExporter(design)
    exporter.draw_fab_lines()

    fab_line = exporter.board.graphic_item[0]
    assert fab_line.layer == "F.Fab"
    assert fab_line.start == Point(x=1, y=2)
    assert fab_line.end == Point(x=3, y=4)


def test_draw_fab_text_adds_board_text_on_fab_layer():
    design = Design("TEST")
    design.layout.fab.append(
        layout_lib.FabText(
            text="FAB NOTE",
            position=layout_lib.Position(x=5, y=6, angle=90),
            height=1.5,
            width=1.2,
            thickness=0.2,
        )
    )

    exporter = kicad.KicadExporter(design)
    exporter.draw_fab_lines()

    fab_text = exporter.board.graphic_item[0]
    assert fab_text.layer == "F.Fab"
    assert fab_text.text == "FAB NOTE"
    assert fab_text.at == pcb.Position(x=5, y=6, angle=90)
    assert fab_text.effects.font.size.height == 1.5
    assert fab_text.effects.font.size.width == 1.2
    assert fab_text.effects.font.thickness == 0.2


def test_module_graphics_are_transformed_and_flipped():
    parent = Design("Parent")
    module = Design("Graphics", "GR")
    module.layout.silk.append(
        layout_lib.SilkLine(
            start=layout_lib.Position(x=1, y=2, angle=0),
            end=layout_lib.Position(x=3, y=2, angle=0),
        )
    )
    module.layout.fab.append(
        layout_lib.FabLine(
            start=layout_lib.Position(x=1, y=0, angle=0),
            end=layout_lib.Position(x=1, y=2, angle=0),
        )
    )
    parent.add_module(module)
    parent.layout.placement["GR1"] = layout_lib.Placement(
        position=layout_lib.Position(x=10, y=20, angle=90),
        layer=layout_lib.Layer.BOTTOM,
    )

    exporter = kicad.KicadExporter(parent)
    exporter.draw_silkscreen_lines()
    exporter.draw_fab_lines()

    silk_line = exporter.board.graphic_item[0]
    fab_line = exporter.board.graphic_item[1]
    assert silk_line.layer == "B.SilkS"
    assert silk_line.start == Point(x=8, y=21)
    assert silk_line.end == Point(x=8, y=23)
    assert fab_line.layer == "B.Fab"
    assert fab_line.start == Point(x=10, y=21)
    assert fab_line.end == Point(x=8, y=21)


def test_add_pour_sets_zone_net_name():
    design = Design("TEST")
    design.layout.outline = layout_lib.BoundingBox(x1=0, y1=0, x2=10, y2=20)
    design.layout.pours.append(layout_lib.PourLayer(net_name="GND", layer=2))

    exporter = kicad.KicadExporter(design)
    exporter.convert_to_kicad(design)

    zone = exporter.board.zone[0]
    assert zone.net == "GND"
    assert exporter.builder.ensure_net("GND").name == "GND"
    assert zone.layer == "B.Cu"


def test_exporter_adds_tracks_arcs_and_polygonal_zones():
    design = Design("TEST")
    design.layout.tracks.extend(
        [
            layout_lib.TrackSegment(
                start=layout_lib.LayoutPoint(1, 2),
                end=layout_lib.LayoutPoint(3, 4),
                width=0.25,
                layer="F.Cu",
                net_name="GND",
            ),
            layout_lib.TrackArc(
                start=layout_lib.LayoutPoint(3, 4),
                mid=layout_lib.LayoutPoint(4, 5),
                end=layout_lib.LayoutPoint(5, 4),
                width=0.15,
                layer="B.Cu",
                net_name="SIG",
                locked=True,
            ),
        ]
    )
    design.layout.zones.append(
        layout_lib.Zone(
            net_name="GND",
            layers=("B.Cu",),
            outline=(
                layout_lib.LayoutPoint(0, 0),
                layout_lib.LayoutPoint(10, 0),
                layout_lib.LayoutPoint(10, 10),
                layout_lib.LayoutPoint(0, 10),
            ),
            name="Ground plane",
            priority=2,
            locked=True,
        )
    )

    exporter = kicad.KicadExporter(design)
    exporter.convert_to_kicad(design)

    assert isinstance(exporter.board.track[0], pcb.Segment)
    assert exporter.board.track[0].net == "GND"
    assert exporter.board.track[0].width == 0.25
    assert isinstance(exporter.board.track[1], pcb.Arc)
    assert exporter.board.track[1].mid == Point(x=4, y=5)
    assert exporter.board.track[1].locked is True
    zone = exporter.board.zone[0]
    assert zone.net == "GND"
    assert zone.layer == "B.Cu"
    assert zone.name == "Ground plane"
    assert zone.priority == 2
    assert zone.locked is True


def test_exporter_rejects_track_on_unavailable_copper_layer():
    design = Design("TEST")
    design.layout.tracks.append(
        layout_lib.TrackSegment(
            start=layout_lib.LayoutPoint(1, 2),
            end=layout_lib.LayoutPoint(3, 4),
            width=0.25,
            layer="In1.Cu",
            net_name="GND",
        )
    )

    with pytest.raises(ValueError, match="In1.Cu.*not available"):
        kicad.KicadExporter(design).convert_to_kicad(design)


def test_layout_net_references_reject_non_string_names():
    design = Design("TEST")
    component = design.add_component(cmp.Component())
    pin = cmp.Pin("CB", 1, component)

    with pytest.raises(TypeError, match="PourLayer.*net_name.*str.*Pin"):
        layout_lib.PourLayer(net_name=pin, layer=1)
    with pytest.raises(TypeError, match="ViaConfig.*net_name.*str.*Pin"):
        layout_lib.ViaConfig(
            location=layout_lib.Position(0, 0, 0),
            net_name=pin,
            hole_size=0.6,
            drill_size=0.3,
        )


def test_layout_net_references_preserve_named_tuple_behavior():
    position = layout_lib.Position(1, 2, 0)
    via = layout_lib.ViaConfig(position, "GND", 0.6, 0.3)
    pour = layout_lib.PourLayer("GND", 1)

    assert tuple(via) == (position, "GND", 0.6, 0.3)
    assert tuple(pour) == ("GND", 1)
    assert via[1] == "GND"
    assert pour[0] == "GND"
    assert pour._replace(layer=2) == layout_lib.PourLayer("GND", 2)

    with pytest.raises(TypeError, match="PourLayer.*net_name.*str.*object"):
        pour._replace(net_name=object())
    with pytest.raises(TypeError, match="ViaConfig.*net_name.*str.*object"):
        layout_lib.ViaConfig._make((position, object(), 0.6, 0.3))


def test_kicad_export_keeps_module_port_connected_resistors_on_parent_net():
    module = Design("LS", "LS", ports=["SIG", "GND"])
    module.add_series_res(module.port["SIG"], "10k", module.port["GND"])
    pulldown = module.add_component(cmp.Resistor("4.7k"))
    module.connect([pulldown.pins[1], module.port["SIG"]], "SIG")
    module.connect([pulldown.pins[2], module.port["GND"]], "GND")

    design = Design("TEST")
    level_shifter = design.add_module(module)
    design.join_net(level_shifter.port["SIG"], "SIG_0")
    design.join_net(level_shifter.port["GND"], "GND")

    exporter = kicad.KicadExporter(design)
    exporter.convert_to_kicad(design)

    pad_nets_by_reference = {
        kicad.get_index(footprint): [
            pad.net.name if pad.net else None for pad in footprint.pads
        ]
        for footprint in exporter.board.footprint
    }
    assert pad_nets_by_reference["LS1_R1"][0] == "SIG_0"
    assert pad_nets_by_reference["LS1_R2"][0] == "SIG_0"
