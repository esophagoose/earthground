import pytest

from common.components import Capacitor, Component, Net, Pin, Resistor
from common.schematic import Design, Ports


def test_ports_initialization():
    ports = Ports(["p1", "P2", "P3"])
    assert hasattr(ports, "p1")
    assert hasattr(ports, "p2")
    assert hasattr(ports, "p3")
    assert ports["p1"] is None
    with pytest.raises(ValueError):
        ports["unknown"]


def test_design_initialization():
    design = Design("TestDesign")
    assert design.name == "TestDesign"
    assert design.short_name == "TestDesign"
    assert design.components == {}
    assert design.modules == []
    assert design.nets != {}
    assert "GND" in design.nets


def test_add_component():
    design = Design("TestDesign")
    resistor = Resistor(1000)
    design.add_component(resistor)
    assert resistor in design.components.values()


def test_add_net():
    design = Design("TestDesign")
    net = design.add_net("VCC")
    assert isinstance(net, Net)
    assert "VCC" in design.nets


def test_connect():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("1", 1, component)
    pin2 = Pin("2", 2, component)
    design.connect([pin1, pin2], "VCC")
    assert pin1 in design.nets["VCC"].connections
    assert pin2 in design.nets["VCC"].connections


def test_add_module():
    parent_design = Design("ParentDesign")
    child_design = Design("ChildDesign")
    parent_design.add_module(child_design)
    assert child_design in parent_design.modules
    assert child_design.short_name.startswith("ChildDesign0")


def test_add_decoupling_cap():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin = Pin("1", 1, component)
    capacitor = Capacitor(1e-6, 50)
    design.add_decoupling_cap(pin, capacitor)
    assert capacitor in design.components.values()
    assert pin in design.nets[f"AutoNet{pin.name}"].connections
    assert capacitor.pins[2] in design.nets["GND"].connections


def test_add_series_res():
    net = "TEST_NET"
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("1", 1, component)
    pin2 = Pin("2", 2, component)
    res = design.add_series_res(pin1, 1000, pin2, net)
    assert isinstance(res, Resistor)
    assert res in design.components.values()
    assert pin1 in design.nets[net].connections
    assert res.pins[1] in design.nets[net].connections
    assert pin2 in design.nets[f"{net}_R"].connections
    assert res.pins[2] in design.nets[f"{net}_R"].connections
