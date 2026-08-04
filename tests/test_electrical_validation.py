from decimal import Decimal

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
    name,
    direction,
    *,
    drive=cmp.DriveStyle.UNSPECIFIED,
    operating=None,
    abs_max=None,
    **kwargs,
):
    return cmp.DigitalPinSpec.single_mode(
        direction,
        name=name,
        drive_style=drive,
        voltage_operating=operating,
        voltage_abs_max=abs_max,
        **kwargs,
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


def test_e2_groups_doubled_package_pads_as_one_logical_driver():
    output_voltage = sv.volts(3.0, typ=3.3, max=3.6, source="regulator DS")
    design = Design("DoubledOutput", "DBL")
    regulator = design.add_component(
        TypedComponent(
            {
                3: power("VOUT", cmp.PowerRole.OUTPUT, voltage=output_voltage),
                4: power("VOUT", cmp.PowerRole.OUTPUT, voltage=output_voltage),
            }
        )
    )
    for pin in regulator.pins.all_with_name("VOUT"):
        design.join_net(pin, "P3V3")

    report = design.check_electrical()
    e2 = [check for check in report.checks if check.rule_id == "E2"]
    resolved = erc.DesignAnalysis(design).nets["P3V3"]

    assert [check.status for check in e2] == [sv.CheckStatus.PASS]
    assert "1 unconditional logical driver(s) across 2 package pad(s)" in e2[0].message
    assert resolved.power_voltage == output_voltage
    assert resolved.voltage == output_voltage


def test_e2_keeps_independent_outputs_as_distinct_drivers():
    voltage = sv.volts(typ=3.3)

    separate_components = Design("SeparateComponents")
    first = separate_components.add_component(
        TypedComponent({1: power("VOUT", cmp.PowerRole.OUTPUT, voltage=voltage)})
    )
    second = separate_components.add_component(
        TypedComponent({1: power("VOUT", cmp.PowerRole.OUTPUT, voltage=voltage)})
    )
    separate_components.connect([first.pins[1], second.pins[1]], "SHARED")
    assert statuses(separate_components.check_electrical(), "E2") == [
        sv.CheckStatus.FAIL
    ]

    separate_names = Design("SeparateNames")
    dual = separate_names.add_component(
        TypedComponent(
            {
                1: power("OUT_A", cmp.PowerRole.OUTPUT, voltage=voltage),
                2: power("OUT_B", cmp.PowerRole.OUTPUT, voltage=voltage),
            }
        )
    )
    separate_names.connect([dual.pins[1], dual.pins[2]], "SHARED")
    assert statuses(separate_names.check_electrical(), "E2") == [sv.CheckStatus.FAIL]


def test_e8_rejects_one_logical_pin_split_across_multiple_nets():
    voltage = sv.volts(typ=3.3)
    design = Design("SplitLogicalPin", "SPLIT")
    regulator = design.add_component(
        TypedComponent(
            {
                3: power("VOUT", cmp.PowerRole.OUTPUT, voltage=voltage),
                4: power("VOUT", cmp.PowerRole.OUTPUT, voltage=voltage),
            }
        )
    )
    design.join_net(regulator.pins[3], "P3V3_A")
    design.join_net(regulator.pins[4], "P3V3_B")

    checks = [
        check for check in design.check_electrical().checks if check.rule_id == "E8"
    ]

    assert [check.status for check in checks] == [sv.CheckStatus.FAIL]
    assert "logical pin VOUT spans nets P3V3_A, P3V3_B" in checks[0].message
    assert "package pads 3, 4" in checks[0].message


def test_doubled_driver_with_inconsistent_voltage_metadata_stays_unresolved():
    design = Design("InconsistentLogicalPin")
    regulator = design.add_component(
        TypedComponent(
            {
                3: power("VOUT", cmp.PowerRole.OUTPUT, voltage=sv.volts(typ=3.3)),
                4: power("VOUT", cmp.PowerRole.OUTPUT, voltage=sv.volts(typ=5.0)),
            }
        )
    )
    design.connect(regulator.pins.all_with_name("VOUT"), "OUTPUT")

    resolved = erc.DesignAnalysis(design).nets["OUTPUT"]

    assert statuses(design.check_electrical(), "E2") == [sv.CheckStatus.PASS]
    assert resolved.power_voltage is None
    assert resolved.voltage is None


def test_doubled_driver_groups_across_hierarchy_and_ignores_dnp_outputs():
    voltage = sv.volts(typ=3.3)
    child = Design("Regulator", "REG", ports=["VOUT"])
    regulator = child.add_component(
        TypedComponent(
            {
                3: power("VOUT", cmp.PowerRole.OUTPUT, voltage=voltage),
                4: power("VOUT", cmp.PowerRole.OUTPUT, voltage=voltage),
            }
        )
    )
    child.connect([*regulator.pins.all_with_name("VOUT"), child.port["VOUT"]], "VOUT")

    board = Design("Board")
    module = board.add_module(child)
    board.join_net(module.port["VOUT"], "P3V3")
    alternate = board.add_component(
        TypedComponent({1: power("VOUT", cmp.PowerRole.OUTPUT, voltage=voltage)})
    )
    alternate.dnp = True
    board.join_net(alternate.pins[1], "P3V3")

    resolved = erc.DesignAnalysis(board).nets["P3V3"]

    assert statuses(board.check_electrical(), "E2") == [sv.CheckStatus.PASS]
    assert resolved.power_voltage == voltage
    assert resolved.voltage == voltage


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


def test_e3_accepts_declared_internal_pull_on_unconnected_input():
    design = Design("InternalBias")
    device = design.add_component(
        TypedComponent(
            {
                1: digital(
                    "ENABLE",
                    cmp.PinDirection.INPUT,
                    internal=cmp.InternalDigitalFeatures(pull_up=True),
                )
            }
        )
    )

    checks = [
        check for check in design.check_electrical().checks if check.rule_id == "E3"
    ]
    assert checks[0].status is sv.CheckStatus.PASS
    assert "internal pull-up or pull-down" in checks[0].message
    assert device.pins[1] not in design.pin_to_net


def test_internal_pull_with_supply_reference_resolves_unconnected_pin_voltage():
    design = Design("InternalBiasVoltage")
    device = design.add_component(
        TypedComponent(
            {
                1: power(
                    "VDD",
                    cmp.PowerRole.INPUT,
                    voltage=sv.volts(3.0, max=3.6),
                ),
                2: digital(
                    "ENABLE",
                    cmp.PinDirection.INPUT,
                    abs_max=sv.volts(min=sv.UNBOUNDED, max=4),
                    internal=cmp.InternalDigitalFeatures(
                        pull_up=True,
                        pull_up_to="VDD",
                        pull_up_resistance=sv.ohms(300_000, typ=300_000, max=300_000),
                        source="datasheet internal pull-up",
                    ),
                ),
            }
        )
    )
    design.join_net(device.pins.by_name("VDD"), "P3V3")
    design.declare_rail("P3V3", sv.volts(3.2, typ=3.3, max=3.4))

    report = design.check_electrical()
    enable_e3 = [
        check
        for check in report.checks
        if check.rule_id == "E3" and "ENABLE" in (check.pin or "")
    ]
    assert [check.status for check in enable_e3] == [sv.CheckStatus.PASS]
    assert statuses(report, "E6") == [sv.CheckStatus.PASS]
    e6 = next(check for check in report.checks if check.rule_id == "E6")
    assert "datasheet internal pull-up" in e6.sources


def test_resistor_pull_and_divider_voltage_inference_is_conservative():
    pull = Design("Pull")
    input_device = pull.add_component(
        TypedComponent(
            {
                1: digital(
                    "NEN",
                    cmp.PinDirection.INPUT,
                    abs_max=sv.volts(min=sv.UNBOUNDED, max=1),
                )
            }
        )
    )
    resistor = pull.add_component(cmp.Resistor("10k"))
    pull.connect([input_device.pins[1], resistor.pins[1]], "NEN")
    pull.join_net(resistor.pins[2], "GND")

    analysis = erc.DesignAnalysis(pull)
    assert analysis.net_for_pin(input_device.pins[1]).voltage.max == 0
    assert statuses(pull.check_electrical(), "E6") == [sv.CheckStatus.PASS]

    divider = Design("Divider")
    input_device = divider.add_component(
        TypedComponent(
            {
                1: digital(
                    "MID",
                    cmp.PinDirection.INPUT,
                    abs_max=sv.volts(min=0, max=2),
                )
            }
        )
    )
    upper = divider.add_component(cmp.Resistor("10k"))
    lower = divider.add_component(cmp.Resistor("10k"))
    divider.connect([input_device.pins[1], upper.pins[1], lower.pins[1]], "MID")
    divider.join_net(upper.pins[2], "P3V3")
    divider.join_net(lower.pins[2], "GND")
    divider.declare_rail("P3V3", sv.volts(3.3, typ=3.3, max=3.3))

    midpoint = erc.DesignAnalysis(divider).net_for_pin(input_device.pins[1]).voltage
    assert midpoint.min == midpoint.typ == midpoint.max == Decimal("1.65")
    assert statuses(divider.check_electrical(), "E6") == [sv.CheckStatus.PASS]


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


def test_hierarchical_erc_uses_parent_rail_and_pullup_once():
    child = Design("Peripheral", "PER", ports=["VCC", "SDA"])
    device = child.add_component(
        TypedComponent(
            {
                1: power(
                    "VCC",
                    cmp.PowerRole.INPUT,
                    voltage=sv.volts(3.0, max=3.6),
                ),
                2: digital(
                    "SDA",
                    cmp.PinDirection.BIDIRECTIONAL,
                    drive=cmp.DriveStyle.OPEN_DRAIN,
                ),
            }
        )
    )
    child.connect([device.pins[1], child.port["VCC"]], "VCC")
    child.connect([device.pins[2], child.port["SDA"]], "SDA")

    parent = Design("Board")
    module = parent.add_module(child)
    parent.join_net(module.port["VCC"], "P3V3")
    parent.join_net(module.port["SDA"], "I2C_SDA")
    pullup = parent.add_component(cmp.Resistor("4.7k"))
    parent.connect([module.port["SDA"], pullup.pins[1]], "I2C_SDA")
    parent.connect([pullup.pins[2], module.port["VCC"]], "P3V3")
    parent.declare_rail("P3V3", sv.volts(3.1, typ=3.3, max=3.5))

    report = parent.check_electrical()
    assert statuses(report, "E1") == [sv.CheckStatus.PASS]
    assert statuses(report, "E5") == [sv.CheckStatus.PASS]

    child.declare_rail("P3V3", sv.volts(1.7, typ=1.8, max=1.9))
    assert statuses(parent.check_electrical(), "E1") == [sv.CheckStatus.UNKNOWN]


def test_e5_requires_pull_down_for_negative_differential_open_drain():
    interface = cmp.PinInterfaceRef(
        interface="PAIR",
        polarity=cmp.DifferentialPolarity.NEGATIVE,
    )
    design = Design("DifferentialOpenDrain")
    device = design.add_component(
        TypedComponent(
            {
                1: digital(
                    "PAIR_N",
                    cmp.PinDirection.BIDIRECTIONAL,
                    drive=cmp.DriveStyle.OPEN_DRAIN,
                    interface=interface,
                )
            }
        )
    )
    pulldown = design.add_component(cmp.Resistor("4.7k"))
    design.connect([device.pins[1], pulldown.pins[1]], "PAIR_N")
    design.join_net(pulldown.pins[2], "GND")

    checks = [
        check for check in design.check_electrical().checks if check.rule_id == "E5"
    ]
    assert checks[0].status is sv.CheckStatus.PASS
    assert "pull-down" in checks[0].message

    wrong = Design("DifferentialOpenDrainWrongBias")
    wrong_device = wrong.add_component(
        TypedComponent(
            {
                1: digital(
                    "PAIR_N",
                    cmp.PinDirection.BIDIRECTIONAL,
                    drive=cmp.DriveStyle.OPEN_DRAIN,
                    interface=interface,
                )
            }
        )
    )
    pullup = wrong.add_component(cmp.Resistor("4.7k"))
    wrong.connect([wrong_device.pins[1], pullup.pins[1]], "PAIR_N")
    wrong.join_net(pullup.pins[2], "P3V3")
    wrong.declare_rail("P3V3", sv.volts(3.1, typ=3.3, max=3.5))
    assert statuses(wrong.check_electrical(), "E5") == [sv.CheckStatus.FAIL]


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

    design.defer_ambient("No thermal ICD is available")
    deferred = design.check_electrical()
    assert deferred.unknowns[0].acknowledgement_reason == "No thermal ICD is available"
    assert deferred.is_valid
    assert design.validate(skip_footprint_check=True, check_electrical=True)

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
