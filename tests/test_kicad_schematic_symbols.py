import earthground.components as cmp
from earthground.exporters.schematic_generation.power_symbols import \
    get_power_symbol_reference
from earthground.exporters.schematic_generation.symbols.kicad_symbol import \
    symbol_reference_for_component
from earthground.exporters.schematic_generation.symbols.symbol import \
    VisualSymbol
from earthground.library.integrated_circuits.io_expanders import tca9535pwr


def test_passive_components_use_builtin_symbol_references():
    resistor_reference = symbol_reference_for_component(cmp.Resistor(1000))
    capacitor_reference = symbol_reference_for_component(cmp.Capacitor(1e-6, 10))
    inductor_reference = symbol_reference_for_component(cmp.Inductor(1e-6))

    assert resistor_reference.library_id == "Device:R"
    assert capacitor_reference.library_id == "Device:C"
    assert inductor_reference.library_id == "Device:L"


def test_non_passive_component_generates_embedded_symbol():
    component = tca9535pwr.TCA9535PWR()
    symbol_reference = symbol_reference_for_component(component)

    assert symbol_reference.library_id.startswith("earthground:")
    assert symbol_reference.symbol is not None
    pins_by_number = {pin.number: pin for pin in symbol_reference.symbol.pins}
    visual_symbol = VisualSymbol.from_component(component)
    left_pin_numbers = {str(pin.index) for pin in visual_symbol.left}
    right_pin_numbers = {str(pin.index) for pin in visual_symbol.right}
    assert pins_by_number["1"].name == component.pins[1].name
    assert pins_by_number["24"].name == component.pins[24].name
    assert all(
        pins_by_number[number].position.angle == 0 for number in left_pin_numbers
    )
    assert all(
        pins_by_number[number].position.angle == 180 for number in right_pin_numbers
    )


def test_known_power_nets_map_to_kicad_power_symbols():
    ground_symbol = get_power_symbol_reference("GND")
    vcc_symbol = get_power_symbol_reference("VCC")

    assert ground_symbol is not None
    assert ground_symbol.library_id == "power:GND"
    assert ground_symbol.symbol is not None
    assert ground_symbol.symbol.isPower is True

    assert vcc_symbol is not None
    assert vcc_symbol.library_id == "power:VCC"
    assert vcc_symbol.symbol is not None
    assert vcc_symbol.symbol.isPower is True


def test_unknown_power_net_returns_none():
    assert get_power_symbol_reference("SYS_3V3") is None
