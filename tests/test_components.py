from decimal import Decimal

import pytest

import earthground.pins as pin_types
from earthground.components import (
    Capacitor,
    Component,
    DigitalMode,
    DigitalPinSpec,
    Net,
    PassivePinSpec,
    Pin,
    PinContainer,
    PinDirection,
    PinSpec,
    PowerPinSpec,
    PowerRole,
    Resistor,
    UnspecifiedPinSpec,
)


def test_resistor_initialization():
    resistor = Resistor("1k")
    assert resistor.value.value == Decimal("1000")


def test_capacitor_initialization():
    capacitor = Capacitor(1e-6, 50)
    assert capacitor.value.value == Decimal("1e-6")
    assert capacitor.voltage.value == Decimal("50")
    assert capacitor.name == "CAP_1uF_50V"


def test_capacitor_name_avoids_float_artifacts():
    capacitor = Capacitor(47e-9, 66)
    assert capacitor.name == "CAP_47nF_66V"


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


def test_pin_identity_uses_index_and_parent_but_not_metadata():
    component = Component()
    pin1 = Pin("GND", 1, component)
    pin2 = Pin("GND", 2, component)
    enriched = Pin(
        "GND",
        1,
        component,
        PowerPinSpec(name="GND", role=PowerRole.GROUND),
    )

    assert pin1 != pin2
    assert hash(pin1) != hash(pin2)
    assert pin1 == enriched
    assert hash(pin1) == hash(enriched)


def test_pin_container_accepts_specs_and_preserves_order():
    component = Component()
    pins = PinContainer.from_dict(
        {
            2: DigitalPinSpec(
                name="OUT",
                modes=(DigitalMode("default", PinDirection.OUTPUT),),
            ),
            1: "IN",
        },
        component,
    )

    assert [pin.index for pin in pins] == [2, 1]
    assert isinstance(pins[2].spec, DigitalPinSpec)
    assert isinstance(pins[1].spec, UnspecifiedPinSpec)


def test_core_passive_pins_are_typed():
    resistor = Resistor("10k")

    assert all(isinstance(pin.spec, PassivePinSpec) for pin in resistor.pins)


def test_components_reexports_pin_api():
    assert Pin is pin_types.Pin
    assert PinSpec is pin_types.PinSpec
    assert PinContainer is pin_types.PinContainer
    assert DigitalPinSpec is pin_types.DigitalPinSpec
    assert PowerPinSpec is pin_types.PowerPinSpec
