import pytest

from earthground.components import Capacitor, Component, Net, Pin, Resistor
from earthground.library.integrated_circuits.io_expanders import tca9535pwr
from earthground.schematic import Design, Ports


def test_ports_initialization():
    ports = Ports(["p1", "P2", "P3"])
    assert hasattr(ports, "p1")
    assert hasattr(ports, "p2")
    assert hasattr(ports, "p3")
    ports["p3"] = 1
    assert ports["p1"] is None
    with pytest.raises(ValueError):
        ports["unknown"]
    with pytest.raises(ValueError):
        ports["unknown"] = 1


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
    design.default_passive_size = "0603"
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


def test_connect_bus():
    design = Design("TestDesign")
    u1 = design.add_component(tca9535pwr.TCA9535PWR())
    u2 = design.add_component(tca9535pwr.TCA9535PWR())
    design.connect_bus(u1.i2c, u2.i2c)
    assert u1.pins.by_name("SDA") in design.nets["I2C0_SDA"].connections
    assert u2.pins.by_name("SDA") in design.nets["I2C0_SDA"].connections


def test_connect_bus_with_name():
    design = Design("TestDesign")
    u1 = design.add_component(tca9535pwr.TCA9535PWR())
    u2 = design.add_component(tca9535pwr.TCA9535PWR())
    u3 = design.add_component(tca9535pwr.TCA9535PWR())
    design.connect_bus(u1.i2c, u2.i2c)
    design.connect_bus(u1.i2c, u3.i2c)
    assert u2.pins.by_name("SDA") in design.nets["I2C0_SDA"].connections
    assert u3.pins.by_name("SDA") in design.nets["I2C0_SDA"].connections


def test_connect_auto_assigned():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("TEST1", 1, component)
    pin2 = Pin("TEST2", 2, component)
    design.connect([pin1, pin2])
    net = design.pin_to_net[pin2].name
    assert net.startswith("AutoNet_"), "Failed to auto-assign name"
    assert pin1 in design.nets[net].connections
    assert pin2 in design.nets[net].connections


def test_connect_assigned_net():
    net = "TEST_NET"
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("TEST1", 1, component)
    pin2 = Pin("TEST2", 2, component)
    design.join_net(pin2, net)
    design.connect([pin1, pin2])
    assert pin1 in design.nets[net].connections
    assert pin2 in design.nets[net].connections


def test_add_module():
    parent_design = Design("ParentDesign")
    parent_design.default_passive_size = "0603"
    child_design = Design("ChildDesign")
    parent_design.add_module(child_design)
    assert child_design in parent_design.modules
    assert child_design.short_name.startswith("ChildDesign0")
    with pytest.raises(ValueError):
        parent_design.add_module("STRING")


def test_add_decoupling_cap():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin = Pin("1", 1, component)
    capacitor = Capacitor(1e-6, 50)
    design.add_decoupling_cap(pin, capacitor)
    assert capacitor in design.components.values()
    assert pin in design.nets[f"AutoNet_{pin.name}"].connections
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


def test_add_series_res_assigned_pin2():
    net = "TEST_NET"
    assigned_net = "DIFFERENT_NET"
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("1", 1, component)
    pin2 = Pin("2", 2, component)
    design.join_net(pin2, assigned_net)
    res = design.add_series_res(pin1, 1000, pin2, net)
    assert isinstance(res, Resistor)
    assert res in design.components.values()
    assert pin1 in design.nets[net].connections
    assert res.pins[1] in design.nets[net].connections
    assert pin2 in design.nets[assigned_net].connections
    assert res.pins[2] in design.nets[assigned_net].connections


def test_get_net_from_pin():
    design = Design("TestDesign")
    resistor = design.add_component(Resistor(1000))
    pin1, pin2 = resistor.pins[1], resistor.pins[2]
    design.join_net(pin1, "CustomNet")
    result = design._get_net_name_from_pin(pin1)
    assert result == "CustomNet", "The net name should be 'CustomNet'"

    # Testing with auto-generated net name
    pin2 = resistor.pins[2]
    auto_net_name = design._get_net_name_from_pin(pin2)
    assert auto_net_name == "AutoNet_2", "Auto-generated net name didn't match"


def test_printing():
    design = Design("TestDesign", "TD", ["1"])
    design.add_component(Resistor(1000))
    design.print_symbol()
    design.print()
