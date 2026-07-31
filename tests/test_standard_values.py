from decimal import Decimal

import pytest

from earthground.standard_values import (
    SiNumber,
    find_closest_ratio,
    get_standard_values,
    voltage_divider,
)
import earthground.standard_values as sv


def test_get_standard_values():
    # Test for E24 series
    values = get_standard_values(24)
    assert len(values) == 24, "E24 series should have 24 values"
    assert 4.7 in values, "4.7 should be in E24 series"

    # Test for E48 series
    values = get_standard_values(48)
    assert len(values) == 48, "E48 series should have 48 values"
    assert 9.09 in values, "9.09 should be in E48 series"


def test_find_closest_ratio():
    closest = sorted(find_closest_ratio(3.5))
    assert closest == [1.6, 5.6]


def test_si_number():
    # Test initialization and string representation
    number = SiNumber(1000, "Ω")
    assert str(number) == "1kΩ", "String representation should be 1kΩ"
    assert repr(number) == "1kΩ", "String representation should be 1kΩ"

    # Test initialization with string and Decimal representation
    number = SiNumber("1kΩ", "Ω")
    assert number.value == Decimal("1000"), "Value should be 1000 for 1kΩ"

    # Test float input is normalized through Decimal formatting
    number = SiNumber(47e-9, "F")
    assert str(number) == "47nF", "Float inputs should format without artifacts"

    # Test fractional values preserve meaningful precision
    number = SiNumber("47.1nF", "F")
    assert str(number) == "47.1nF", "Fractional values should keep the decimal part"

    # Test incorrect unit
    with pytest.raises(ValueError):
        SiNumber("UNDEFINED", "Hz")


def test_voltage_divider_logs_debug_when_error_within_threshold(caplog):
    caplog.set_level("DEBUG", logger="earthground.standard_values")

    voltage_divider(3.3, 0.9, 10)

    assert "Voltage divider: 3.3V -> 0.9V" in caplog.text
    assert "Error: 2.94%" in caplog.text
    assert "exceeds 3%" not in caplog.text


def test_voltage_divider_warns_when_error_exceeds_threshold(caplog):
    caplog.set_level("DEBUG", logger="earthground.standard_values")

    voltage_divider(3.3, 1.8, 10)

    assert "Voltage divider: 3.3V -> 1.8V" in caplog.text
    assert "Voltage divider error 3.70% exceeds 3%" in caplog.text


def test_value_bounds_normalizes_units_and_equality():
    millivolts = sv.ValueBounds("mV", min=1000, typ=1200, max=1500)
    volts = sv.ValueBounds("V", min=1, typ=1.2, max=1.5)

    assert millivolts == volts
    assert hash(millivolts) == hash(volts)
    assert millivolts.units == "V"
    assert millivolts.typ == Decimal("1.2")
    assert millivolts.covers(1200) is sv.CheckStatus.PASS
    assert sv.volts(min="900mV", max="1.1V").min == Decimal("0.9")


def test_value_bounds_distinguishes_unknown_and_unbounded():
    unknown = sv.volts(max=5)
    open_ended = sv.volts(min=sv.UNBOUNDED, max=5)

    assert unknown.covers(3) is sv.CheckStatus.UNKNOWN
    assert open_ended.covers(3) is sv.CheckStatus.PASS
    assert open_ended.covers(6) is sv.CheckStatus.FAIL
    with pytest.raises(sv.IndeterminateBoundsError):
        3 in unknown


def test_value_bounds_interval_arithmetic_and_dimensions():
    voltage = sv.volts(1, typ=1.5, max=2, source="voltage source")
    current = sv.amps(2, typ=2.5, max=3, source="current source")
    power = voltage * current

    assert power.units == "W"
    assert power.min == Decimal("2")
    assert power.typ == Decimal("3.75")
    assert power.max == Decimal("6")
    assert power.source == ("voltage source", "current source")

    resistance = sv.ohms(2, typ=3, max=4)
    assert (voltage / resistance).units == "A"
    assert ((current * current) * resistance).units == "W"
    assert (sv.ValueBounds("°C/W", min=2, max=3) * power).units == "°C"

    with pytest.raises(ValueError, match="division by zero"):
        voltage / sv.ohms(-1, max=1)


def test_value_bounds_tolerance_overlap_margin_and_worst_case():
    bounds = sv.volts(nominal=1.8, tolerance_pct=5)

    assert bounds.to_list() == [
        Decimal("1.71"),
        Decimal("1.8"),
        Decimal("1.89"),
    ]
    assert bounds.overlaps(sv.volts(1.85, max=2)) is sv.CheckStatus.PASS
    assert bounds.overlaps(sv.volts(2, max=2.1)) is sv.CheckStatus.FAIL
    assert bounds.margin(1.8) == (Decimal("0.09"), Decimal("0.09"))
    assert bounds.worst_case(sv.BoundDirection.UPPER) == Decimal("1.89")
