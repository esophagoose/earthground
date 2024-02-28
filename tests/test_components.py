import pytest

from common.components import Capacitor, Component, Net, Pin, Resistor


def test_resistor_initialization():
    resistor = Resistor("1k")
    assert resistor.value.value == 1000


def test_capacitor_initialization():
    capacitor = Capacitor(1e-6, 50)
    assert capacitor.value.value == 1e-6
    assert capacitor.voltage.value == 50


def test_pin_initialization():
    component = Component()
    pin = Pin("1", 1, component)
    assert pin.name == "1"
    assert pin.index == 1
    assert pin.parent == component


def test_net_initialization():
    net = Net("VCC")
    assert net.name == "VCC"
    assert len(net.connections) == 0


def test_net_add_connection():
    net = Net("VCC")
    component = Component()
    pin = Pin("1", 1, component)
    net.add(pin)
    assert net.name == "VCC"
    assert len(net.connections) == 1
    assert pin in net.connections
