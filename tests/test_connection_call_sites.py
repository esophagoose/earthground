import earthground.components as cmp
from earthground.library.integrated_circuits.controllers.ch334 import (
    bus_powered_design,
)
from earthground.library.integrated_circuits.logic.level_shifters.lsf0102 import (
    LSF0102PartNumbers,
    generate_design,
)
from earthground.library.integrated_circuits.voltage_regulators.linear.ap7330 import (
    AP7330,
)


def test_ch334_crystal_connections_use_connect_list_api():
    crystal = cmp.Component()
    crystal.name = "12MHz Crystal"
    crystal.frequency = 12.0
    crystal.pins = cmp.PinContainer.from_count(2, crystal)

    design = bus_powered_design(crystal)
    hub = next(
        component
        for component in design.components.values()
        if component.mpn == "CH334F"
    )

    assert (
        design.pin_to_net[hub.pins.by_name("XI")] is design.pin_to_net[crystal.pins[1]]
    )
    assert (
        design.pin_to_net[hub.pins.by_name("XO")] is design.pin_to_net[crystal.pins[2]]
    )


def test_ap7330_reference_design_places_and_connects_adjustment_resistors():
    design = AP7330.reference_design(3.3)
    ldo = next(
        component
        for component in design.components.values()
        if isinstance(component, AP7330)
    )
    resistors = [
        component
        for component in design.components.values()
        if isinstance(component, cmp.Resistor)
    ]

    assert len(resistors) == 2
    assert (
        design.pin_to_net[ldo.pins.by_name("VOUT")]
        is design.pin_to_net[resistors[0].pins[1]]
    )
    assert (
        design.pin_to_net[ldo.pins.by_name("ADJ")]
        is design.pin_to_net[resistors[0].pins[2]]
    )
    assert (
        design.pin_to_net[ldo.pins.by_name("ADJ")]
        is design.pin_to_net[resistors[1].pins[1]]
    )
    assert (
        design.pin_to_net[ldo.pins.by_name("GND")]
        is design.pin_to_net[resistors[1].pins[2]]
    )


def test_lsf0102_reference_design_owns_every_connected_component():
    first = generate_design(LSF0102PartNumbers.LSF0102DCTR)
    second = generate_design(LSF0102PartNumbers.LSF0102DCTR)

    assert not first._validate_design(False)
    assert not second._validate_design(False)
    assert (
        len(
            [
                component
                for component in first.components.values()
                if isinstance(component, cmp.Resistor)
            ]
        )
        == 1
    )
