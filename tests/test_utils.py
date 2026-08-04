import pytest

import earthground.utils as utils


@pytest.mark.parametrize(
    ("voltage", "net_name"),
    [
        (5, "P5V0"),
        (3.3, "P3V3"),
        (-1.2, "N1V2"),
        (0, "P0V0"),
        (0.000001, "P0V000001"),
    ],
)
def test_power_net_name_voltage_conversion(voltage, net_name):
    assert utils.voltage_to_net_name(voltage) == net_name
    assert utils.power_net_name_to_voltage(net_name) == voltage


@pytest.mark.parametrize(
    "net_name",
    ["", "VCC", "P3", "P3V", "P3V3V0", "p3V3", "P-3V3"],
)
def test_power_net_name_to_voltage_rejects_invalid_names(net_name):
    with pytest.raises(ValueError, match="Cannot convert net name"):
        utils.power_net_name_to_voltage(net_name)


@pytest.mark.parametrize("voltage", [float("inf"), float("-inf"), float("nan")])
def test_voltage_to_net_name_rejects_nonfinite_values(voltage):
    with pytest.raises(ValueError, match="Cannot convert voltage"):
        utils.voltage_to_net_name(voltage)
