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
    assert footprint.pads[0].number == "1"
    assert footprint.pads[0].net.name == "NET_A"
    assert footprint.pads[1].net.name == "NET_B"


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

    text_items = [
        item for item in footprint.graphicItems if isinstance(item, fp.FpText)
    ]
    silk_text = [item for item in text_items if item.layer.endswith(".SilkS")]
    fab_text = [item for item in text_items if item.layer.endswith(".Fab")]
    assert silk_text
    assert all(item.hide for item in silk_text)
    assert any(not item.hide for item in fab_text)


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

    assert reference.text == "U99"
    assert reference.layer == "F.SilkS"
    assert reference.hide is True


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

    text_items = [
        item for item in footprint.graphicItems if isinstance(item, fp.FpText)
    ]
    silk_text = [item for item in text_items if item.layer.endswith(".SilkS")]
    fab_text = [item for item in text_items if item.layer.endswith(".Fab")]
    assert any(not item.hide for item in silk_text)
    assert fab_text
    assert all(item.hide for item in fab_text)


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
        for footprint in exporter.board.footprints
        for item in footprint.graphicItems
        if isinstance(item, fp.FpText)
    ]
    assert all(
        item.hide for item in text_items if item.layer.endswith((".SilkS", ".Fab"))
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

    silk_line = exporter.board.graphicItems[0]
    fab_line = exporter.board.graphicItems[1]
    assert silk_line.layer == "B.SilkS"
    assert silk_line.start == fp.Position(X=8, Y=21, angle=0)
    assert silk_line.end == fp.Position(X=8, Y=23, angle=0)
    assert fab_line.layer == "B.Fab"
    assert fab_line.start == fp.Position(X=10, Y=21, angle=0)
    assert fab_line.end == fp.Position(X=8, Y=21, angle=0)


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
