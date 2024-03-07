import kiutils.footprint as fp

import earthground.components as cmp
import earthground.exporters.kicad as kicad
import earthground.footprints.passives as pfp
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
    assert footprint.pads[0].number == "1"
    assert footprint.pads[0].net.name == "NET_A"
    assert footprint.pads[0].position == fp.Position(X=-0.9125, Y=0)
    assert footprint.pads[0].size == fp.Position(X=1.025, Y=1.4)
    assert footprint.pads[1].number == "2"
    assert footprint.pads[1].net.name == "NET_B"
    assert footprint.pads[1].position == fp.Position(X=0.9125, Y=0)
    assert footprint.pads[1].size == fp.Position(X=1.025, Y=1.4)
    assert len(footprint.pads) == 2
