import pytest

import common.utils as utils


def test_electrical_bool_to_int():
    eb = utils.ElectricalBool("VCC", "GND")
    assert eb.to_int("VCC") == 1, "VCC should return 1"
    assert eb.to_int("GND") == 0, "GND should return 0"
    with pytest.raises(ValueError):
        eb.to_int("Undefined")


def test_electrical_bool_to_net():
    eb = utils.ElectricalBool("VCC", "GND")
    assert eb.to_net(1) == "VCC", "1 should return VCC"
    assert eb.to_net(0) == "GND", "0 should return GND"


def test_add():
    assert utils.add((1, 2), (3, 4)) == (4, 6)
    with pytest.raises(AssertionError):
        utils.add((1, 2), (3, 4, 5))


def test_rotate():
    assert utils.rotate((1, 0), (0, 0), 90) == pytest.approx(
        (-0, 1)
    ), "90 degree rotation failed"
    assert utils.rotate((1, 1), (1, 1), 45) == pytest.approx(
        (1, 1)
    ), "45 degree rotation around self failed"


def test_scale():
    assert utils.scale((10, 20), 10) == (1, 2), "Scaling by 10 failed"


def test_four_corner_rect():
    center, width, height = utils.four_corner_rect(0, 0, 10, 10)
    assert center == (5, 5), "Center calculation failed"
    assert width == 10, "Width calculation failed"
    assert height == 10, "Height calculation failed"
