from decimal import Decimal

import pytest

import earthground.components as cmp
from earthground.library.integrated_circuits.logic.level_shifters.lsf0102 import (
    LSF0102,
    LSF0102PartNumbers,
)
from earthground.ratings import Ratings
import earthground.standard_values as sv


def test_ratings_are_open_dimension_checked_and_immutable():
    ratings = Ratings(vin=sv.volts(1, max=5), custom_limit=sv.ohms(max=10))

    assert ratings["vin"].units == "V"
    assert ratings["custom_limit"].units == "Ω"
    with pytest.raises(TypeError):
        ratings["vin"] = sv.volts(max=6)
    with pytest.raises(ValueError, match="snake-case"):
        Ratings({"Supply Voltage": sv.volts(max=5)})
    with pytest.raises(ValueError, match="must use V"):
        Ratings(vin=sv.amps(max=1))


def test_component_defaults_and_lsf0102_reference_migration():
    assert not cmp.Component().abs_max
    part = LSF0102(LSF0102PartNumbers.LSF0102DCTR)

    assert isinstance(part.abs_max, Ratings)
    assert isinstance(part.recommended, Ratings)
    assert part.abs_max["i_channel"].max == Decimal("0.128")
    assert part.recommended["ta"] == sv.celsius(-40, max=125)
    assert isinstance(part.pins.by_name("A1").spec, cmp.DigitalPinSpec)
    assert part.pins.by_name("A1").erc.directions == frozenset(
        (cmp.PinDirection.BIDIRECTIONAL,)
    )
    assert part.pins.by_name("EN").erc.directions == frozenset(
        (cmp.PinDirection.INPUT,)
    )
    assert isinstance(part.pins.by_name("VREF_A").spec, cmp.PowerPinSpec)
    assert part.pins.by_name("VREF_A").erc.power_role is cmp.PowerRole.INPUT
