import pytest

from earthground.standard_values import (SiNumber, find_closest_ratio,
                                    get_standard_values)


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
    assert str(number) == "1.0kΩ", "String representation should be 1kΩ"
    assert repr(number) == "1.0kΩ", "String representation should be 1kΩ"

    # Test initialization with string and float representation
    number = SiNumber("1kΩ", "Ω")
    assert number.value == 1000, "Value should be 1000 for 1kΩ"

    # Test incorrect unit
    with pytest.raises(ValueError):
        SiNumber("UNDEFINED", "Hz")
