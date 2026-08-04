import pytest

from earthground.library.integrated_circuits.io_expanders import tca9535pwr


@pytest.mark.parametrize("address", range(8))
def test_generate_design_sets_address_pins(address):
    design = tca9535pwr.generate_design(address=address, interrupt_pullup=None)
    expander = next(
        component
        for component in design.components.values()
        if isinstance(component, tca9535pwr.TCA9535PWR)
    )

    for bit in range(3):
        expected_net = "VCC" if address & (1 << bit) else "GND"
        assert expander.pins.by_name(f"A{bit}").net.name == expected_net
    assert expander.address == (1 << 6) | address
