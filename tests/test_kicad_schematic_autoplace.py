import earthground.components as cmp
from earthground.exporters.schematic_generation.autoplace import \
    autoplace_design_page
from earthground.schematic import Design


def test_autoplace_is_deterministic_for_components_and_sheets():
    design = Design("Parent")
    design.add_component(cmp.Resistor(1000))
    design.add_component(cmp.Capacitor(1e-6, 10))

    module = Design("Child", "CH", ports=["VIN", "VOUT", "GND"])
    design.add_module(module)

    placement_a = autoplace_design_page(design)
    placement_b = autoplace_design_page(design)

    assert placement_a == placement_b
    assert len(placement_a.components) == 2
    assert len(placement_a.sheets) == 1


def test_sheet_pins_are_assigned_to_consistent_edges():
    design = Design("Parent")
    module = Design("PowerModule", "PWR", ports=["VIN", "VOUT", "GND"])
    design.add_module(module)

    placement = autoplace_design_page(design)
    sheet = placement.sheets[0]
    pins_by_name = {pin.name: pin for pin in sheet.pins}

    assert pins_by_name["VIN"].side == "left"
    assert pins_by_name["VOUT"].side == "right"
    assert pins_by_name["GND"].side == "right"
