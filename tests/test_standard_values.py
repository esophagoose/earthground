from decimal import Decimal

import pytest

from earthground.standard_values import (SiNumber, find_closest_ratio,
                                         get_standard_values, voltage_divider)


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
