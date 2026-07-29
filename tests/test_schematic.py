import pytest

import earthground.footprints.passives as passives
from earthground.components import Capacitor, Component, Net, Pin, Resistor
from earthground.library.integrated_circuits.io_expanders import tca9535pwr
from earthground.schematic import Design, Ports, SchematicValidationError


def _capture_design_state(design):
    return {
        "components": tuple(design.components.items()),
        "component_state": tuple(
            (
                component,
                component.parent,
                component.refdes,
                component.refdes_postfix,
            )
            for component in design.components.values()
        ),
        "modules": tuple(design.modules),
        "nets": tuple(
            (name, net, frozenset(net.connections)) for name, net in design.nets.items()
        ),
        "pin_to_net": tuple(design.pin_to_net.items()),
        "children": tuple(_capture_design_state(module) for module in design.modules),
    }


def test_ports_initialization():
    design = Design("PortsTest", ports=["p1", "P2", "P3"])
    ports = design.port
    assert hasattr(ports, "p1")
    assert hasattr(ports, "P2")
    assert hasattr(ports, "P3")
    assert ports["p1"].name == "p1"
    assert ports["P2"].name == "P2"
    with pytest.raises(ValueError):
        ports["unknown"]
    with pytest.raises(RuntimeError):
        ports["unknown"] = 1


def test_design_initialization():
    design = Design("TestDesign")
    assert design.name == "TestDesign"
    assert design.short_name == "TestDesign"
    assert design.components == {}
    assert design.modules == []
    assert design.nets != {}
    assert "GND" in design.nets


def test_add_component():
    design = Design("TestDesign")
    design.default_passive_size = "0603"
    resistor = Resistor(1000)
    design.add_component(resistor)
    assert resistor in design.components.values()


def test_add_component_preserves_custom_capacitor_footprint():
    design = Design("TestDesign")
    capacitor = Capacitor(1e-6, 50)
    custom_footprint = passives.PassiveSmd(passives.PassivePackage.C0805)
    capacitor.footprint = custom_footprint
    capacitor.package_size = "0603"

    design.add_component(capacitor)

    assert capacitor.footprint is custom_footprint


def test_add_net():
    design = Design("TestDesign")
    net = design.add_net("VCC")
    assert isinstance(net, Net)
    assert "VCC" in design.nets


def test_connect():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("1", 1, component)
    pin2 = Pin("2", 2, component)
    design.connect([pin1, pin2], "VCC")
    assert pin1 in design.nets["VCC"].connections
    assert pin2 in design.nets["VCC"].connections


def test_connect_bus():
    design = Design("TestDesign")
    u1 = design.add_component(tca9535pwr.TCA9535PWR())
    u2 = design.add_component(tca9535pwr.TCA9535PWR())
    with pytest.raises(AttributeError, match="_asdict"):
        design.connect_bus([u1.i2c, u2.i2c])


def test_connect_bus_with_name():
    design = Design("TestDesign")
    u1 = design.add_component(tca9535pwr.TCA9535PWR())
    u2 = design.add_component(tca9535pwr.TCA9535PWR())
    u3 = design.add_component(tca9535pwr.TCA9535PWR())
    with pytest.raises(AttributeError, match="_asdict"):
        design.connect_bus([u1.i2c, u2.i2c])
    with pytest.raises(AttributeError, match="_asdict"):
        design.connect_bus([u1.i2c, u3.i2c])


def test_connect_auto_assigned():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("TEST1", 1, component)
    pin2 = Pin("TEST2", 2, component)
    design.connect([pin1, pin2])
    net = design.pin_to_net[pin2].name
    assert net.startswith("AutoNet_"), "Failed to auto-assign name"
    assert pin1 in design.nets[net].connections
    assert pin2 in design.nets[net].connections


def test_connect_assigned_net():
    net = "TEST_NET"
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("TEST1", 1, component)
    pin2 = Pin("TEST2", 2, component)
    design.join_net(pin2, net)
    design.connect([pin1, pin2])
    assert pin1 in design.nets[net].connections
    assert pin2 in design.nets[net].connections


def test_add_module():
    parent_design = Design("ParentDesign")
    parent_design.default_passive_size = "0603"
    child_design = Design("ChildDesign")
    parent_design.add_module(child_design)
    assert child_design in parent_design.modules
    assert child_design.short_name.startswith("ChildDesign1")
    with pytest.raises(ValueError):
        parent_design.add_module("STRING")


def test_add_decoupling_cap():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin = Pin("1", 1, component)
    capacitor = Capacitor(1e-6, 50)
    pin.add_decoupling_capacitor(capacitor)
    assert capacitor in design.components.values()
    assert pin in design.nets[f"AutoNet_{pin.name}"].connections
    assert capacitor.pins[2] in design.nets["GND"].connections


def test_add_series_res():
    net = "TEST_NET"
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("1", 1, component)
    pin2 = Pin("2", 2, component)
    res = design.add_series_res(pin1, 1000, pin2, net)
    assert isinstance(res, Resistor)
    assert res in design.components.values()
    assert pin1 in design.nets[net].connections
    assert res.pins[1] in design.nets[net].connections
    assert pin2 in design.nets[f"{net}_R"].connections
    assert res.pins[2] in design.nets[f"{net}_R"].connections


def test_add_series_res_assigned_pin2():
    net = "TEST_NET"
    assigned_net = "DIFFERENT_NET"
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("1", 1, component)
    pin2 = Pin("2", 2, component)
    design.join_net(pin2, assigned_net)
    res = design.add_series_res(pin1, 1000, pin2, net)
    assert isinstance(res, Resistor)
    assert res in design.components.values()
    assert pin1 in design.nets[net].connections
    assert res.pins[1] in design.nets[net].connections
    assert pin2 in design.nets[assigned_net].connections
    assert res.pins[2] in design.nets[assigned_net].connections


def test_get_net_from_pin():
    design = Design("TestDesign")
    resistor = design.add_component(Resistor(1000))
    pin1, pin2 = resistor.pins[1], resistor.pins[2]
    design.join_net(pin1, "CustomNet")
    result = design._get_net_name_from_pin(pin1)
    assert result == "CustomNet", "The net name should be 'CustomNet'"

    # Testing with auto-generated net name
    pin2 = resistor.pins[2]
    auto_net_name = design._get_net_name_from_pin(pin2)
    assert auto_net_name == "AutoNet_2", "Auto-generated net name didn't match"


def test_printing():
    design = Design("TestDesign", "TD", ["1"])
    design.add_component(Resistor(1000))
    design.print_symbol()
    design.print()


def test_validate_raises_schematic_validation_error_and_logs(caplog):
    caplog.set_level("ERROR", logger="earthground.schematic")
    design = Design("TestDesign")
    design.add_component(Component())

    with pytest.raises(SchematicValidationError) as excinfo:
        design.validate()

    assert excinfo.value.design_name == "TestDesign"
    assert "No footprint" in str(excinfo.value)
    assert "VALIDATION FAILED" in caplog.text


def test_validate_reports_single_connection_in_flat_design():
    design = Design("TestDesign")
    resistor = design.add_component(Resistor("1k"))
    design.join_net(resistor.pins[1], "DANGLING")

    with pytest.raises(SchematicValidationError) as excinfo:
        design.validate(
            skip_footprint_check=True,
            check_no_single_connections=True,
        )

    assert excinfo.value.errors == [
        f"Single connection! Net<DANGLING> - {{{resistor.pins[1]!r}}}"
    ]


def test_validate_resolves_module_connections_without_mutating_design():
    parent = Design("Parent")
    module = parent.add_module(Design("Module", "MOD", ports=["OUT"]))
    parent.join_net(module.port["OUT"], "PARENT_OUT")

    resistor = module.add_component(Resistor("1k"))
    module.connect([resistor.pins[1], module.port["OUT"]], "MODULE_OUT")

    state_before_validation = _capture_design_state(parent)

    parent.validate(
        skip_footprint_check=True,
        check_no_single_connections=True,
    )

    assert _capture_design_state(parent) == state_before_validation


def test_validate_reports_nested_single_connection_without_mutating_design():
    leaf = Design("Leaf", "LEAF", ports=["OUT"])
    resistor = leaf.add_component(Resistor("1k"))
    leaf.connect([resistor.pins[1], leaf.port["OUT"]], "LEAF_OUT")
    leaf.join_net(resistor.pins[2], "DANGLING")

    middle = Design("Middle", "MID", ports=["OUT"])
    leaf = middle.add_module(leaf)
    middle.connect([leaf.port["OUT"], middle.port["OUT"]], "MIDDLE_OUT")

    top = Design("Top", "TOP")
    middle = top.add_module(middle)
    top.join_net(middle.port["OUT"], "TOP_OUT")

    state_before_validation = _capture_design_state(top)

    with pytest.raises(SchematicValidationError) as excinfo:
        top.validate(
            skip_footprint_check=True,
            check_no_single_connections=True,
        )

    assert len(excinfo.value.errors) == 1
    assert "Net<MID1_LEAF1_DANGLING>" in excinfo.value.errors[0]
    assert repr(resistor.pins[2]) in excinfo.value.errors[0]
    assert _capture_design_state(top) == state_before_validation
