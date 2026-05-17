from earthground.components import Resistor
from earthground.schematic import Design, flatten


def _build_level_shifter() -> Design:
    design = Design("LS", "LS", ports=["SIG", "GND"])
    design.add_series_res(design.port["SIG"], "10k", design.port["GND"])
    pulldown = design.add_component(Resistor("4.7k"))
    design.connect([pulldown.pins[1], design.port["SIG"]], "SIG")
    design.connect([pulldown.pins[2], design.port["GND"]], "GND")
    return design


def _build_switch() -> Design:
    design = Design("LoadSwitch", "LS", ports=["VIN", "VOUT", "GND"])
    switch = design.add_component(Resistor("1k"))
    design.connect([switch.pins[1], design.port["VIN"]], "VIN")
    design.connect([switch.pins[2], design.port["VOUT"]])
    design.connect([design.port["GND"]], "GND")
    return design


def _build_child_with_internal_net() -> Design:
    design = Design("Child", "CH")
    resistor = design.add_component(Resistor("1k"))
    design.join_net(resistor.pins[1], "INTERNAL")
    return design


def _build_child_with_ported_net() -> Design:
    design = Design("Child", "CH", ports=["OUT"])
    resistor = design.add_component(Resistor("1k"))
    design.connect([resistor.pins[1], design.port["OUT"]], "INTERNAL")
    return design


def _build_parent_with_child_modules() -> Design:
    design = Design("Parent", "PARENT")
    design.add_module(_build_child_with_internal_net())
    design.add_module(_build_child_with_internal_net())
    return design


def _build_parent_with_ported_child() -> Design:
    design = Design("Parent", "PARENT", ports=["OUT"])
    child = design.add_module(_build_child_with_ported_net())
    design.connect([child.port["OUT"], design.port["OUT"]], "LOCAL")
    return design


def _build_switched_supply() -> Design:
    design = Design("SwitchedSupply", "VS", ports=["VIN", "SAFE_3V3", "GND"])
    load_switch = design.add_module(_build_switch())
    design.connect([load_switch.port["VIN"], design.port["VIN"]], "P3V3")
    design.connect([load_switch.port["VOUT"]], "3V3_SW")
    design.connect([load_switch.port["GND"], design.port["GND"]], "GND")

    limit = design.add_component(Resistor("47"))
    design.connect([limit.pins[1]], "3V3_SW")
    design.connect([limit.pins[2], design.port["SAFE_3V3"]], "SAFE_3V3")
    return design


def test_add_module_scopes_existing_module_nets():
    parent = Design("Parent")
    module = Design("Module", "MOD")

    # Create nets inside the module before it is added to the parent
    r = module.add_component(Resistor(1000))
    module.join_net(r.pins[1], "NET1")
    module.join_net(r.pins[2], "NET2")

    # After add_module, nets should be scoped with the module's short_name
    parent.add_module(module)

    assert "MOD1_NET1" in module.nets
    assert "MOD1_NET2" in module.nets
    assert any(pin is r.pins[1] for pin in module.nets["MOD1_NET1"].connections)
    assert any(pin is r.pins[2] for pin in module.nets["MOD1_NET2"].connections)


def test_flatten_merges_port_connected_nets_into_parent_net():
    parent = Design("Parent")
    module = Design("Module", "MOD", ["OUT"])
    parent.add_module(module)

    resistor = module.add_component(Resistor(1000))
    module.join_net(resistor.pins[1], "NET1")
    module.join_net(resistor.pins[2], "NET2")
    module.join_net(module.port.OUT, "NET1")
    parent.join_net(module.port.OUT, "PARENT_OUT")

    flatten(parent)

    # Port-connected NET1 should merge into the parent net name
    assert "PARENT_OUT" in parent.nets
    assert "MOD1_NET1" not in parent.nets
    assert any(pin is resistor.pins[1] for pin in parent.nets["PARENT_OUT"].connections)

    # Non-port NET2 becomes a plain parent net; the name is inherited as-is
    # from the module into the parent during flattening.
    assert "NET2" in parent.nets
    assert any(pin is resistor.pins[2] for pin in parent.nets["NET2"].connections)


def test_connecting_port_to_existing_net_merges_all_existing_connections():
    level_shifter = _build_level_shifter()
    series_resistor = level_shifter.components["R1"]
    pulldown = level_shifter.components["R2"]

    assert (
        level_shifter.pin_to_net[series_resistor.pins[1]] is level_shifter.nets["SIG"]
    )
    assert level_shifter.pin_to_net[pulldown.pins[1]] is level_shifter.nets["SIG"]
    assert (
        level_shifter.pin_to_net[level_shifter.port["SIG"]] is level_shifter.nets["SIG"]
    )
    assert {
        series_resistor.pins[1],
        pulldown.pins[1],
        level_shifter.port["SIG"],
    }.issubset(level_shifter.nets["SIG"].connections)


def test_parent_port_net_rename_keeps_all_module_connections():
    parent = Design("Parent")
    level_shifter = parent.add_module(_build_level_shifter())

    parent.join_net(level_shifter.port["SIG"], "SIG_0")

    series_resistor = level_shifter.components["R1"]
    pulldown = level_shifter.components["R2"]
    assert (
        level_shifter.pin_to_net[series_resistor.pins[1]] is level_shifter.nets["SIG_0"]
    )
    assert level_shifter.pin_to_net[pulldown.pins[1]] is level_shifter.nets["SIG_0"]


def test_adding_nested_module_propagates_scoped_net_names_through_child_ports():
    board = Design("Board")
    supply = board.add_module(_build_switched_supply())
    load_switch = supply.modules[0]
    load_switch_component = load_switch.components["R1"]
    limit = supply.components["R1"]

    assert "VS1_3V3_SW" in supply.nets
    assert "VS1_3V3_SW" in load_switch.nets
    assert supply.pin_to_net[limit.pins[1]].name == "VS1_3V3_SW"
    assert load_switch.pin_to_net[load_switch_component.pins[2]].name == "VS1_3V3_SW"


def test_repeated_nested_modules_scope_child_internal_nets():
    top = Design("Top", "TOP")
    parent1 = top.add_module(_build_parent_with_child_modules())
    parent2 = top.add_module(_build_parent_with_child_modules())

    assert [module.short_name for module in parent1.modules] == ["CH1", "CH2"]
    assert [module.short_name for module in parent2.modules] == ["CH1", "CH2"]
    assert "PARENT1_CH1_INTERNAL" in parent1.modules[0].nets
    assert "PARENT1_CH2_INTERNAL" in parent1.modules[1].nets
    assert "PARENT2_CH1_INTERNAL" in parent2.modules[0].nets
    assert "PARENT2_CH2_INTERNAL" in parent2.modules[1].nets

    flatten(top)

    assert "PARENT1_CH1_INTERNAL" in top.nets
    assert "PARENT1_CH2_INTERNAL" in top.nets
    assert "PARENT2_CH1_INTERNAL" in top.nets
    assert "PARENT2_CH2_INTERNAL" in top.nets
    assert "CH1_INTERNAL" not in top.nets
    assert "CH2_INTERNAL" not in top.nets
    assert any(refdes.endswith("_CH1_PARENT1") for refdes in top.components)
    assert any(refdes.endswith("_CH1_PARENT2") for refdes in top.components)
    assert not any("_PARENT1_CH1_PARENT1" in refdes for refdes in top.components)


def test_nested_modules_added_after_parent_instantiation_scope_child_nets():
    top = Design("Top", "TOP")
    parent1 = top.add_module(Design("Parent", "PARENT"))
    parent2 = top.add_module(Design("Parent", "PARENT"))

    parent1.add_module(_build_child_with_internal_net())
    parent2.add_module(_build_child_with_internal_net())

    assert "PARENT1_CH1_INTERNAL" in parent1.modules[0].nets
    assert "PARENT2_CH1_INTERNAL" in parent2.modules[0].nets

    flatten(top)

    assert "PARENT1_CH1_INTERNAL" in top.nets
    assert "PARENT2_CH1_INTERNAL" in top.nets
    assert "CH1_INTERNAL" not in top.nets


def test_nested_port_connected_nets_still_merge_through_parent_ports():
    top = Design("Top", "TOP")
    parent1 = top.add_module(_build_parent_with_ported_child())
    parent2 = top.add_module(_build_parent_with_ported_child())
    top.join_net(parent1.port["OUT"], "TOP1")
    top.join_net(parent2.port["OUT"], "TOP2")
    parent1_resistor = parent1.modules[0].components["R1"]
    parent2_resistor = parent2.modules[0].components["R1"]

    flatten(top)

    assert parent1_resistor.pins[1] in top.nets["TOP1"].connections
    assert parent2_resistor.pins[1] in top.nets["TOP2"].connections
    assert parent1_resistor.pins[1] not in top.nets["TOP2"].connections
    assert parent2_resistor.pins[1] not in top.nets["TOP1"].connections


def test_merge_nets_propagates_target_name_through_child_ports():
    parent = Design("Parent")
    module = parent.add_module(_build_switch())
    parent.connect([module.port["VOUT"]], "SOURCE")
    parent.add_net("TARGET")

    parent.merge_nets("SOURCE", "TARGET")

    switch = module.components["R1"]
    assert module.pin_to_net[switch.pins[2]].name == "TARGET"
