from decimal import Decimal

import pytest

import earthground.components as cmp
import earthground.standard_values as sv


def test_mode_dependent_differential_digital_pin():
    spec = cmp.DigitalPinSpec(
        name="DB0P",
        description=(
            "CSI-2/DSI lane 0 differential positive output. "
            "Supports DSI LP back channel."
        ),
        modes=(
            cmp.DigitalMode(
                "HS",
                cmp.PinDirection.OUTPUT,
                drive_style=cmp.DriveStyle.PUSH_PULL,
            ),
            cmp.DigitalMode("LP", cmp.PinDirection.BIDIRECTIONAL),
        ),
        ratings=cmp.DigitalPinRatings(
            voltage_abs_max=sv.volts(min=sv.UNBOUNDED, max=1.4),
        ),
        internal=cmp.InternalDigitalFeatures(
            pull_up=False,
            pull_down=False,
            termination="100Ω differential termination in HS mode",
        ),
        interface=cmp.PinInterfaceRef(
            interface="DB0",
            polarity=cmp.DifferentialPolarity.POSITIVE,
        ),
    )

    assert spec.domain is cmp.SignalDomain.DIGITAL
    assert spec.erc_characteristics().directions == frozenset(
        (cmp.PinDirection.OUTPUT, cmp.PinDirection.BIDIRECTIONAL)
    )
    assert spec.erc_characteristics().voltage_abs_max.max == Decimal("1.4")
    assert spec.internal.pull_up is False
    assert spec.interface.polarity is cmp.DifferentialPolarity.POSITIVE


def test_differential_interface_is_component_level():
    interface = cmp.DifferentialInterfaceSpec(
        name="DB0",
        positive="DB0P",
        negative="DB0N",
        target_impedance=sv.ohms(nominal=100, tolerance_pct=10),
        unused_policy=cmp.UnusedPolicy.LEAVE_UNCONNECTED,
        required_external="Route as a differential pair to the D-PHY sink",
    )
    component = cmp.Component()
    component.interfaces[interface.name] = interface

    assert component.interfaces["DB0"].target_impedance.typ == Decimal("100")
    with pytest.raises(ValueError, match="must be distinct"):
        cmp.DifferentialInterfaceSpec(
            name="BAD",
            positive="P",
            negative="P",
        )


def test_analog_power_passive_and_no_connect_specs():
    analog = cmp.AnalogPinSpec.input(
        name="ADC0",
        ratings=cmp.AnalogPinRatings(
            voltage_operating=sv.volts(0, max=3.3),
        ),
        input_impedance=sv.ohms(min=1_000_000, max=sv.UNBOUNDED),
    )
    power = cmp.PowerPinSpec(
        name="P1V8",
        role=cmp.PowerRole.INPUT,
        voltage=sv.volts(1.7, typ=1.8, max=1.9),
    )
    passive = cmp.PassivePinSpec(name="PAD")
    no_connect = cmp.NoConnectPinSpec(name="NC")

    assert analog.domain is cmp.SignalDomain.ANALOG
    assert analog.erc_characteristics().directions == frozenset(
        (cmp.PinDirection.INPUT,)
    )
    assert power.erc_characteristics().power_role is cmp.PowerRole.INPUT
    assert passive.domain is cmp.SignalDomain.PASSIVE
    assert (
        no_connect.erc_characteristics().connection
        is cmp.ConnectionPolicy.MUST_NOT_CONNECT
    )


def test_single_mode_digital_factories_share_base_ratings():
    spec = cmp.DigitalPinSpec.output(
        name="IRQ",
        drive_style=cmp.DriveStyle.OPEN_DRAIN,
        voltage_operating=sv.volts(0, max=3.3),
    )

    assert isinstance(spec.ratings, cmp.BasePinRatings)
    assert isinstance(cmp.AnalogPinRatings(), cmp.BasePinRatings)
    assert spec.modes == (
        cmp.DigitalMode(
            "default",
            cmp.PinDirection.OUTPUT,
            drive_style=cmp.DriveStyle.OPEN_DRAIN,
        ),
    )
    assert spec.ratings.voltage_operating == sv.volts(0, max=3.3)


def test_pin_spec_validation_rejects_invalid_domain_data():
    with pytest.raises(ValueError, match="at least one mode"):
        cmp.DigitalPinSpec(name="EMPTY", modes=())
    with pytest.raises(ValueError, match="input_impedance must use Ω"):
        cmp.AnalogPinSpec.input(
            name="ADC",
            input_impedance=sv.volts(max=3.3),
        )
    with pytest.raises(ValueError, match="current_max must use A"):
        cmp.PowerPinSpec(
            name="VCC",
            role=cmp.PowerRole.INPUT,
            current_max=sv.volts(max=1),
        )
