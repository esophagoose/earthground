import kiutils.footprint as fp

import earthground.components as cmp
import earthground.exporters.kicad as kicad
import earthground.footprints.passives as pfp
import earthground.layout as layout_lib
from earthground.schematic import Design


def test_to_position():
    assert kicad.to_position([1, 2]) == fp.Position(X=1, Y=2)


def test_parse_footprint():
    design = Design("TEST")
    component = cmp.Resistor(100)
    component.footprint = pfp.PassiveSmd(pfp.PassivePackage.R0805)
    design.add_component(component)
    design.join_net(component.pins[1], "NET_A")
    design.join_net(component.pins[2], "NET_B")
    footprint = kicad.KicadExporter(design).parse_footprint(design, component)

    assert isinstance(footprint, fp.Footprint)
    assert footprint.entryName == "RES_100.0Ω"
    assert footprint.properties["MPN"] == ""
    assert footprint.pads[0].number == "1"
    # assert footprint.pads[0].net.name == "NET_A"
    # assert footprint.pads[0].position == fp.Position(X=-0.9125, Y=0)
    # assert footprint.pads[0].size == fp.Position(X=1.025, Y=1.4)
    # assert footprint.pads[1].number == "2"
    # assert footprint.pads[1].net.name == "NET_B"
    # assert footprint.pads[1].position == fp.Position(X=0.9125, Y=0)
    # assert footprint.pads[1].size == fp.Position(X=1.025, Y=1.4)
    # assert len(footprint.pads) == 2


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

    fab_line = exporter.board.graphicItems[0]
    assert fab_line.layer == "F.Fab"
    assert fab_line.start == fp.Position(X=1, Y=2, angle=0)
    assert fab_line.end == fp.Position(X=3, Y=4, angle=0)


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

    fab_text = exporter.board.graphicItems[0]
    assert fab_text.layer == "F.Fab"
    assert fab_text.text == "FAB NOTE"
    assert fab_text.position == fp.Position(X=5, Y=6, angle=90)
    assert fab_text.effects.font.height == 1.5
    assert fab_text.effects.font.width == 1.2
    assert fab_text.effects.font.thickness == 0.2


def test_add_pour_sets_zone_net_name():
    design = Design("TEST")
    design.layout.outline = layout_lib.BoundingBox(x1=0, y1=0, x2=10, y2=20)
    design.layout.pours.append(layout_lib.PourLayer(net_name="GND", layer=2))

    exporter = kicad.KicadExporter(design)
    exporter.convert_to_kicad(design)

    zone = exporter.board.zones[0]
    assert zone.netName == "GND"
    assert zone.net == exporter._added_nets["GND"].number
    assert zone.layers == ["B.Cu"]
