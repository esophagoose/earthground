import kiutils.footprint as fp

import earthground.components as cmp
import earthground.exporters.kicad as kicad
import earthground.footprints.passives as pfp
import earthground.layout as layout_lib
from earthground.importers.kicad import KicadFootprint
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
    assert footprint.entryName == "RES_100Ω"
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

    zone = exporter.board.zones[0]
    assert zone.netName == "GND"
    assert zone.net == exporter._added_nets["GND"].number
    assert zone.layers == ["B.Cu"]


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
        kicad.get_index_fptext(footprint).text: [
            pad.net.name if pad.net else None for pad in footprint.pads
        ]
        for footprint in exporter.board.footprints
    }
    assert pad_nets_by_reference["LS1_R1"][0] == "SIG_0"
    assert pad_nets_by_reference["LS1_R2"][0] == "SIG_0"
