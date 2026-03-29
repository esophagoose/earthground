from earthground.components import Resistor
from earthground.schematic import Design, flatten


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
