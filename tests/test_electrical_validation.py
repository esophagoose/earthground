import pytest

import earthground.components as cmp
import earthground.erc as erc
from earthground.ratings import Ratings
import earthground.standard_values as sv
from earthground.schematic import (
    Design,
    ElectricalCheck,
    ElectricalReport,
    SchematicValidationError,
)


class TypedComponent(cmp.Component):
    def __init__(self, pins, recommended=None):
        super().__init__()
        self.name = "TYPED"
        self.pins = cmp.PinContainer.from_dict(pins, self)
        if recommended is not None:
            self.recommended = recommended


def statuses(report, rule_id):
    return [check.status for check in report.checks if check.rule_id == rule_id]


def digital(
    name, direction, *, drive=cmp.DriveStyle.UNSPECIFIED, operating=None, abs_max=None
):
    return cmp.DigitalPinSpec.single_mode(
        direction,
        name=name,
        drive_style=drive,
        voltage_operating=operating,
        voltage_abs_max=abs_max,
    )


def power(name, role, *, voltage=None, abs_max=None):
    return cmp.PowerPinSpec(
        name=name,
        role=role,
        voltage=voltage,
        abs_max=abs_max,
    )


def analog(name, direction=cmp.PinDirection.INPUT, *, abs_max=None):
    return cmp.AnalogPinSpec(
        name=name,
        direction=direction,
        ratings=cmp.AnalogPinRatings(voltage_abs_max=abs_max),
    )


def test_schematic_reexports_erc_report_api():
    assert ElectricalCheck is erc.ElectricalCheck
    assert ElectricalReport is erc.ElectricalReport


def test_e1_supply_compatibility_and_typ_only_unknown():
    design = Design("Power")
    source = design.add_component(
        TypedComponent(
            {
                1: power(
                    "OUT",
                    cmp.PowerRole.OUTPUT,
                    voltage=sv.volts(3.2, typ=3.3, max=3.4),
                )
            }
        )
    )
    sink = design.add_component(
        TypedComponent(
            {
                1: power(
                    "VCC",
                    cmp.PowerRole.INPUT,
                    voltage=sv.volts(3.0, max=3.6),
                )
            }
        )
    )
    design.connect([source.pins[1], sink.pins[1]], "P3V3")

    assert statuses(design.check_electrical(), "E1") == [sv.CheckStatus.PASS]

    source.pins[1].spec = power(
        "OUT",
        cmp.PowerRole.OUTPUT,
        voltage=sv.volts(typ=3.3),
    )
    assert statuses(design.check_electrical(), "E1") == [sv.CheckStatus.UNKNOWN]

    design.declare_rail("P3V3", sv.volts(4.5, max=5))
    assert statuses(design.check_electrical(), "E1") == [sv.CheckStatus.FAIL]


def test_e2_driver_conflict_and_conditional_exemptions():
    design = Design("Drivers")
    first = design.add_component(
        TypedComponent({1: digital("A", cmp.PinDirection.OUTPUT)})
    )
    second = design.add_component(TypedComponent({1: power("B", cmp.PowerRole.OUTPUT)}))
    conditional = design.add_component(
        TypedComponent(
            {
                1: digital(
                    "C",
                    cmp.PinDirection.OUTPUT,
                    drive=cmp.DriveStyle.TRI_STATE,
                )
            }
        )
    )
    design.connect([first.pins[1], second.pins[1], conditional.pins[1]], "BUS")

    conditional_three = design.add_component(
        TypedComponent(
            {
                1: digital(
                    "D",
                    cmp.PinDirection.OUTPUT,
                    drive=cmp.DriveStyle.TRI_STATE,
                )
            }
        )
    )
    conditional_two = design.add_component(
        TypedComponent({1: digital("D", cmp.PinDirection.BIDIRECTIONAL)})
    )
    design.connect([conditional_three.pins[1], conditional_two.pins[1]], "CONDITIONAL")

    assert statuses(design.check_electrical(), "E2") == [sv.CheckStatus.FAIL]


def test_e3_external_drive_and_unconnected_input():
    design = Design("Inputs")
    driven = design.add_component(
        TypedComponent({1: digital("RX", cmp.PinDirection.INPUT)})
    )
    floating = design.add_component(
        TypedComponent({1: digital("IRQ", cmp.PinDirection.INPUT)})
    )
    design.join_net(driven.pins[1], "RX")
    design.declare_external_drive("RX", sv.volts(0, max=3.3))

    assert statuses(design.check_electrical(), "E3") == [
        sv.CheckStatus.PASS,
        sv.CheckStatus.FAIL,
    ]
    assert floating.pins[1] not in design.pin_to_net


def test_e4_no_connect_pin():
    design = Design("NoConnect")
    component = design.add_component(
        TypedComponent({1: cmp.NoConnectPinSpec(name="NC")})
    )
    assert statuses(design.check_electrical(), "E4") == [sv.CheckStatus.PASS]

    design.join_net(component.pins[1], "ACCIDENT")
    assert statuses(design.check_electrical(), "E4") == [sv.CheckStatus.FAIL]


def test_e5_open_drain_requires_populated_resistor_to_positive_rail():
    design = Design("OpenDrain")
    device = design.add_component(
        TypedComponent(
            {
                1: digital(
                    "SDA",
                    cmp.PinDirection.OUTPUT,
                    drive=cmp.DriveStyle.OPEN_DRAIN,
                )
            }
        )
    )
    receiver = design.add_component(
        TypedComponent({1: digital("SDA_IN", cmp.PinDirection.INPUT)})
    )
    pullup = design.add_component(cmp.Resistor("4.7k"))
    design.connect([device.pins[1], receiver.pins[1], pullup.pins[1]], "SDA")
    design.join_net(pullup.pins[2], "P3V3")
    design.declare_rail("P3V3", sv.volts(3.1, typ=3.3, max=3.5))

    assert statuses(design.check_electrical(), "E5") == [sv.CheckStatus.PASS]
    assert statuses(design.check_electrical(), "E3") == [sv.CheckStatus.PASS]

    pullup.dnp = True
    assert statuses(design.check_electrical(), "E5") == [sv.CheckStatus.FAIL]
    assert statuses(design.check_electrical(), "E3") == [sv.CheckStatus.FAIL]


def test_e6_absolute_max_uses_resolved_voltage_and_provenance():
    design = Design("AbsMax")
    component = design.add_component(
        TypedComponent(
            {
                1: analog(
                    "IO",
                    abs_max=sv.volts(
                        min=sv.UNBOUNDED,
                        max=2,
                        source="datasheet section 5",
                    ),
                )
            }
        )
    )
    unresolved = design.add_component(
        TypedComponent(
            {
                1: analog(
                    "UNRESOLVED",
                    abs_max=sv.volts(min=sv.UNBOUNDED, max=5),
                )
            }
        )
    )
    design.join_net(component.pins[1], "P3V3")
    design.declare_rail("P3V3", sv.volts(3.1, max=3.5))

    e6_checks = [
        check for check in design.check_electrical().checks if check.rule_id == "E6"
    ]
    check = e6_checks[0]
    assert check.status is sv.CheckStatus.FAIL
    assert check.sources == ("datasheet section 5",)
    assert e6_checks[1].status is sv.CheckStatus.UNKNOWN
    assert unresolved.pins[1] not in design.pin_to_net

    design.declare_rail("P3V3", sv.volts(1.7, max=1.9))
    assert statuses(design.check_electrical(), "E6") == [
        sv.CheckStatus.PASS,
        sv.CheckStatus.UNKNOWN,
    ]


def test_e7_requires_declared_ambient_and_validate_is_strict():
    design = Design("Temperature")
    design.add_component(
        TypedComponent(
            {},
            recommended=Ratings(ta=sv.celsius(-40, max=85)),
        )
    )

    assert statuses(design.check_electrical(), "E7") == [sv.CheckStatus.UNKNOWN]
    with pytest.raises(SchematicValidationError, match="E7 Unknown"):
        design.validate(skip_footprint_check=True, check_electrical=True)

    design.declare_ambient(sv.celsius(-20, max=70))
    assert statuses(design.check_electrical(), "E7") == [sv.CheckStatus.PASS]
    assert design.validate(skip_footprint_check=True, check_electrical=True)

    design.declare_ambient(sv.celsius(-20, max=100))
    assert statuses(design.check_electrical(), "E7") == [sv.CheckStatus.FAIL]


def test_electrical_validation_is_opt_in_and_coverage_is_recursive():
    parent = Design("Parent")
    legacy = parent.add_component(TypedComponent({1: "LEGACY"}))
    child = Design("Child")
    child.add_component(TypedComponent({1: digital("OUT", cmp.PinDirection.OUTPUT)}))
    child.declare_rail("P1V8", sv.volts(1.7, max=1.9))
    parent.add_module(child)

    # Untyped pins affect coverage but do not create electrical Unknown results.
    assert parent.validate(skip_footprint_check=True) == list(
        parent.components.values()
    ) + list(child.components.values())
    coverage = parent.electrical_coverage()
    assert coverage == {
        "pins_typed": 1,
        "pins_total": 2,
        "rails_declared": 1,
        "ratings_present": 0,
    }
    assert isinstance(legacy.pins[1].spec, cmp.UnspecifiedPinSpec)
