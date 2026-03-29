import earthground.components as cmp
from earthground.exporters.schematic_generation.kicad_schematic import (
    build_schematic_bundle,
    design_to_kicad_schematic,
)
from earthground.schematic import Design


def build_simple_design() -> Design:
    design = Design("Simple")
    left = design.add_component(cmp.Resistor(1000))
    right = design.add_component(cmp.Resistor(2200))
    design.connect([left.pins[2], right.pins[1]], "SIG")
    return design


def build_hierarchical_design() -> Design:
    parent = Design("Parent")
    module = Design("ChildModule", "CH", ports=["VIN", "VOUT", "GND"])

    resistor = module.add_component(cmp.Resistor(1000))
    capacitor = module.add_component(cmp.Capacitor(1e-6, 10))
    module.connect([module.port["VIN"], resistor.pins[1]], "VIN")
    module.connect([resistor.pins[2], capacitor.pins[1], module.port["VOUT"]], "VOUT")
    module.connect([capacitor.pins[2], module.port["GND"]], "GND")

    parent.add_module(module)
    parent.join_net(module.port["VIN"], "VIN")
    parent.join_net(module.port["VOUT"], "VOUT")
    parent.join_net(module.port["GND"], "GND")
    return parent


def build_power_and_multidrop_design() -> Design:
    design = Design("PowerAndBus")
    resistor = design.add_component(cmp.Resistor(1000))
    capacitor = design.add_component(cmp.Capacitor(1e-6, 10))
    inductor = design.add_component(cmp.Inductor(1e-6))

    design.connect([resistor.pins[1], capacitor.pins[1], inductor.pins[1]], "BUS")
    design.connect([resistor.pins[2]], "GND")
    design.connect([capacitor.pins[2]], "GND")
    design.connect([inductor.pins[2]], "RETURN")
    return design


def build_overlapping_direct_nets_design() -> Design:
    design = Design("Overlap")
    r1 = design.add_component(cmp.Resistor(1000))
    r2 = design.add_component(cmp.Resistor(1000))
    r3 = design.add_component(cmp.Resistor(1000))
    r4 = design.add_component(cmp.Resistor(1000))

    design.connect([r1.pins[2], r3.pins[1]], "NET_A")
    design.connect([r2.pins[2], r4.pins[1]], "NET_B")
    return design


def _assert_wire_is_orthogonal(wire) -> None:
    for start, end in zip(wire.points, wire.points[1:]):
        assert start.X == end.X or start.Y == end.Y


def _all_wires(bundle):
    for page in bundle.pages:
        for item in page.schematic.graphicalItems:
            if getattr(item, "type", None) == "wire":
                yield item


def _assert_no_collinear_overlap(wires) -> None:
    segments = []
    for wire in wires:
        start, end = wire.points
        if start.Y == end.Y:
            orientation = "horizontal"
            track = start.Y
            interval = tuple(sorted((start.X, end.X)))
        else:
            orientation = "vertical"
            track = start.X
            interval = tuple(sorted((start.Y, end.Y)))
        segments.append((orientation, track, interval))

    for index, (orientation, track, interval) in enumerate(segments):
        for other_orientation, other_track, other_interval in segments[index + 1 :]:
            if orientation != other_orientation or track != other_track:
                continue
            overlap_start = max(interval[0], other_interval[0])
            overlap_end = min(interval[1], other_interval[1])
            assert overlap_start >= overlap_end


def test_single_page_design_uses_direct_wire_for_simple_net():
    schematic = design_to_kicad_schematic(build_simple_design())
    wires = [item for item in schematic.graphicalItems if item.type == "wire"]

    assert len(wires) == 3
    for wire in wires:
        assert len(wire.points) == 2
        _assert_wire_is_orthogonal(wire)

    start = wires[0].points[0]
    first_bend = wires[0].points[1]
    second_bend = wires[1].points[1]
    end = wires[2].points[1]
    expected_midpoint_x = (start.X + end.X) / 2
    assert first_bend.X == expected_midpoint_x
    assert second_bend.X == expected_midpoint_x
    assert first_bend.Y == start.Y
    assert second_bend.Y == end.Y


def test_hierarchical_design_generates_sheet_and_child_labels():
    bundle = build_schematic_bundle(build_hierarchical_design())

    assert len(bundle.child_schematics) == 1
    assert bundle.root.sheets[0].pins[0].name == "VIN"
    assert bundle.child_schematics[0].hierarchicalLabels[0].text == "VIN"
    for wire in _all_wires(bundle):
        assert len(wire.points) == 2
        _assert_wire_is_orthogonal(wire)


def test_ground_uses_power_symbol_and_multidrop_uses_labels():
    bundle = build_schematic_bundle(build_power_and_multidrop_design())

    assert any(symbol.entryName == "GND" for symbol in bundle.root.libSymbols)
    assert bundle.root.labels
    for wire in _all_wires(bundle):
        assert len(wire.points) == 2
        _assert_wire_is_orthogonal(wire)


def test_direct_routes_avoid_overlapping_tracks_for_different_nets():
    bundle = build_schematic_bundle(build_overlapping_direct_nets_design())
    wires = [item for item in bundle.root.graphicalItems if item.type == "wire"]

    assert wires
    _assert_no_collinear_overlap(wires)


def test_passives_use_builtin_symbols_without_local_shadow_defs():
    bundle = build_schematic_bundle(build_simple_design())

    assert all(symbol.libId != "Device:R" for symbol in bundle.root.libSymbols)
    passive_symbols = [
        symbol for symbol in bundle.root.schematicSymbols if symbol.libId == "Device:R"
    ]
    assert len(passive_symbols) == 2
    assert all(symbol.position.angle == 90 for symbol in passive_symbols)


def test_all_placed_symbols_explicitly_set_unit_one():
    bundle = build_schematic_bundle(build_hierarchical_design())

    for page in bundle.pages:
        assert page.schematic.schematicSymbols
        assert all(symbol.unit == 1 for symbol in page.schematic.schematicSymbols)
