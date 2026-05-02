from earthground.components import Resistor
from earthground.schematic import Design, flatten


def _build_level_shifter() -> Design:
    design = Design("LS", "LS", ports=["SIG", "GND"])
    design.add_series_res(design.port["SIG"], "10k", design.port["GND"])
    pulldown = design.add_component(Resistor("4.7k"))
    design.connect([pulldown.pins[1], design.port["SIG"]], "SIG")
    design.connect([pulldown.pins[2], design.port["GND"]], "GND")
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
