import pytest

import earthground.footprints.passives as passives
from earthground.components import Capacitor, Component, Net, Pin, Resistor
from earthground.library.integrated_circuits.io_expanders import tca9535pwr
from earthground.schematic import (
    Design,
    Ports,
    SchematicConnectionError,
    SchematicValidationError,
)


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


def test_net_name_must_be_a_nonempty_string():
    with pytest.raises(TypeError, match="Net.*name.*str.*object"):
        Net(object())
    with pytest.raises(ValueError, match="Net.*name.*cannot be empty"):
        Net("")

    net = Net("VCC")
    with pytest.raises(TypeError, match="Net.*name.*str.*object"):
        net.name = object()
    assert net.name == "VCC"


def test_add_net_rejects_invalid_or_duplicate_names_without_mutating_design():
    design = Design("TestDesign")
    original_ground = design.nets["GND"]

    with pytest.raises(TypeError, match="add_net.*name.*str.*object"):
        design.add_net(object())
    with pytest.raises(ValueError, match="net 'GND' already exists"):
        design.add_net("GND")

    assert design.nets == {"GND": original_ground}


def test_net_registry_views_are_read_only_and_live():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin = Pin("1", 1, component)
    nets_view = design.nets
    pin_to_net_view = design.pin_to_net

    design.join_net(pin, "SIGNAL")

    assert design.nets is nets_view
    assert design.pin_to_net is pin_to_net_view
    assert nets_view.get("SIGNAL") is design.nets["SIGNAL"]
    assert dict(nets_view.items())["SIGNAL"] is design.nets["SIGNAL"]
    assert "SIGNAL" in nets_view.keys()
    assert design.nets["SIGNAL"] in nets_view.values()
    assert pin_to_net_view.get(pin) is design.nets["SIGNAL"]
    assert len(nets_view) == 2
    assert sorted(nets_view) == ["GND", "SIGNAL"]

    with pytest.raises(TypeError):
        design.nets["OTHER"] = Net("OTHER")
    with pytest.raises(TypeError):
        del design.nets["SIGNAL"]
    with pytest.raises(AttributeError):
        design.nets.pop("SIGNAL")
    with pytest.raises(AttributeError):
        design.nets.clear()
    with pytest.raises(AttributeError):
        design.nets = {}

    with pytest.raises(TypeError):
        design.pin_to_net[pin] = design.nets["GND"]
    with pytest.raises(TypeError):
        del design.pin_to_net[pin]
    with pytest.raises(AttributeError):
        design.pin_to_net.pop(pin)
    with pytest.raises(AttributeError):
        design.pin_to_net.clear()
    with pytest.raises(AttributeError):
        design.pin_to_net = {}


def test_mutating_apis_preserve_registered_net_identity():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("1", 1, component)
    pin2 = Pin("2", 2, component)

    def assert_registry_invariant():
        assert all(
            design.nets.get(net.name) is net for net in design.pin_to_net.values()
        )

    design.add_net("UNUSED")
    assert_registry_invariant()

    design.join_net(pin1, "SIGNAL")
    assert_registry_invariant()

    design.connect([pin2], "SECOND")
    assert_registry_invariant()

    design.change_net_name("UNUSED", "RENAMED")
    assert_registry_invariant()

    design.merge_nets("SECOND", "SIGNAL")
    assert_registry_invariant()


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


def test_connect_auto_assigned_names_are_unique_per_connection():
    design = Design("TestDesign")
    first = design.add_component(Resistor("1k"))
    second = design.add_component(Resistor("1k"))

    design.connect([first.pins[1], first.pins[2]])
    design.connect([second.pins[1], second.pins[2]])

    assert design.pin_to_net[first.pins[1]].name == "AutoNet_1"
    assert design.pin_to_net[second.pins[1]].name == "AutoNet_1_2"
    assert design.pin_to_net[first.pins[1]] is not design.pin_to_net[second.pins[1]]


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


def test_join_net_rejects_pin_as_net_name_without_mutating_design():
    design = Design("TestDesign")
    capacitor = design.add_component(Capacitor(1e-6, 50))
    buck = design.add_component(Component())
    cb_pin = Pin("CB", 1, buck)

    with pytest.raises(
        TypeError,
        match=r"join_net\(\) argument 'net_name' must be a str, got Pin",
    ):
        design.join_net(capacitor.pins[1], cb_pin)

    assert set(design.nets) == {"GND"}
    assert capacitor.pins[1] not in design.pin_to_net
    assert cb_pin not in design.pin_to_net


def test_join_net_rejects_pin_from_unplaced_component():
    design = Design("TestDesign")
    unplaced = Resistor(1000)

    with pytest.raises(SchematicConnectionError, match="does not belong"):
        design.join_net(unplaced.pins[1], "VCC")

    assert set(design.nets) == {"GND"}
    assert unplaced.pins[1] not in design.pin_to_net


def test_join_net_rejects_pin_from_another_design():
    first = Design("First")
    second = Design("Second")
    resistor = second.add_component(Resistor(1000))

    with pytest.raises(SchematicConnectionError, match="does not belong"):
        first.join_net(resistor.pins[1], "VCC")

    assert set(first.nets) == {"GND"}
    assert resistor.pins[1] not in first.pin_to_net


def test_change_net_name_rejects_invalid_name_without_mutating_design():
    design = Design("TestDesign")
    original_net = design.add_net("BOOT")

    with pytest.raises(TypeError, match="change_net_name.*new_net_name.*str.*object"):
        design.change_net_name("BOOT", object())

    assert design.nets["BOOT"] is original_net
    assert set(design.nets) == {"GND", "BOOT"}


def test_merge_nets_rejects_invalid_result_name_without_mutating_design():
    design = Design("TestDesign")
    source = design.add_net("SOURCE")
    target = design.add_net("TARGET")

    with pytest.raises(TypeError, match="merge_nets.*name.*str.*object"):
        design.merge_nets("SOURCE", "TARGET", name=object())

    assert design.nets["SOURCE"] is source
    assert design.nets["TARGET"] is target


@pytest.mark.parametrize("net_name", [0, False, object()])
def test_connect_rejects_non_string_net_name_without_mutating_design(net_name):
    design = Design("TestDesign")
    resistor = design.add_component(Resistor(1000))

    with pytest.raises(TypeError, match="connect.*net_name.*str"):
        design.connect([resistor.pins[1]], net_name)

    assert set(design.nets) == {"GND"}
    assert resistor.pins[1] not in design.pin_to_net


def test_connect_rejects_empty_net_name_without_mutating_design():
    design = Design("TestDesign")
    resistor = design.add_component(Resistor(1000))

    with pytest.raises(ValueError, match="connect.*net_name.*cannot be empty"):
        design.connect([resistor.pins[1]], "")

    assert set(design.nets) == {"GND"}
    assert resistor.pins[1] not in design.pin_to_net


def test_connect_validates_every_pin_before_mutating_design():
    design = Design("TestDesign")
    resistor = design.add_component(Resistor(1000))

    with pytest.raises(SchematicConnectionError, match="Invalid pin: object"):
        design.connect([resistor.pins[1], object()], "PARTIAL")

    assert "PARTIAL" not in design.nets
    assert resistor.pins[1] not in design.pin_to_net


def test_set_pins_validates_every_net_name_before_mutating_design():
    design = Design("TestDesign")
    resistor = design.add_component(Resistor(1000))

    with pytest.raises(TypeError, match="set_pins.*net_name.*str.*object"):
        resistor.set_pins(["VALID", object()])

    assert set(design.nets) == {"GND"}
    assert resistor.pins[1] not in design.pin_to_net
    assert resistor.pins[2] not in design.pin_to_net


def test_connection_helpers_validate_before_adding_components():
    design = Design("TestDesign")
    component = design.add_component(Component())
    pin1 = Pin("ONE", 1, component)
    pin2 = Pin("TWO", 2, component)
    original_components = dict(design.components)

    with pytest.raises(TypeError, match="add_series_res.*net_name.*str.*Pin"):
        design.add_series_res(pin1, 1000, pin2, net_name=pin2)

    capacitor = Capacitor(1e-6, 50)
    with pytest.raises(
        TypeError,
        match="add_decoupling_capacitor.*net_name.*str.*Pin",
    ):
        pin1.add_decoupling_capacitor(capacitor, net_name=pin2)

    assert design.components == original_components
    assert not capacitor.is_in_design
    assert set(design.nets) == {"GND"}


def test_add_pullup_resistor_places_supplied_resistor():
    design = Design("TestDesign")
    target = design.add_component(Resistor(1000))
    pullup = Resistor("10k")

    result = design.add_pullup_resistor(target.pins[1], pullup, "VCC")

    assert result is pullup
    assert pullup.is_in_design
    assert pullup in design.components.values()
    assert design.pin_to_net[pullup.pins[1]].name == "VCC"
    assert design.pin_to_net[pullup.pins[2]] is design.pin_to_net[target.pins[1]]


def test_design_decoupling_helper_requires_explicit_net_name():
    design = Design("Power")
    capacitor = Capacitor("100n", 10)

    with pytest.raises(TypeError, match="missing 1 required positional argument"):
        design.add_decoupling_capacitor(capacitor)

    assert not capacitor.is_in_design
    assert set(design.nets) == {"GND"}


def test_set_ports_validates_every_connection_before_mutating_design():
    design = Design("TestDesign", ports=["GOOD", "BAD"])

    with pytest.raises(ValueError, match="Invalid connection type for port 'BAD'"):
        design.set_ports({"GOOD": "VALID", "BAD": object()})

    assert set(design.nets) == {"GND"}
    assert design.port["GOOD"] not in design.pin_to_net
    assert design.port["BAD"] not in design.pin_to_net


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


def test_add_series_res_uses_unique_names_for_unconnected_destinations():
    design = Design("TestDesign")
    source = design.add_component(Resistor("1k"))
    first_target = design.add_component(Resistor("1k"))
    second_target = design.add_component(Resistor("1k"))

    first = design.add_series_res(source.pins[1], "100", first_target.pins[1], "SOURCE")
    second = design.add_series_res(
        source.pins[1], "100", second_target.pins[1], "SOURCE"
    )

    assert design.pin_to_net[first.pins[2]].name == "SOURCE_R"
    assert design.pin_to_net[second.pins[2]].name == "SOURCE_R_2"
    assert (
        design.pin_to_net[first_target.pins[1]]
        is not design.pin_to_net[second_target.pins[1]]
    )


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


def test_validate_rejects_corrupt_net_registry():
    design = Design("TestDesign")
    resistor = design.add_component(Resistor(1000))
    design.join_net(resistor.pins[1], "SIGNAL")
    connected_net = design.nets["SIGNAL"]
    design._nets["SIGNAL"] = Net("SIGNAL")

    with pytest.raises(SchematicValidationError) as excinfo:
        design.validate(skip_footprint_check=True)

    assert "unregistered net" in str(excinfo.value)
    assert design.pin_to_net[resistor.pins[1]] is connected_net


def test_validate_rejects_non_string_net_registry_key():
    design = Design("TestDesign")
    malformed_key = object()
    design._nets[malformed_key] = Net("MALFORMED")

    with pytest.raises(SchematicValidationError) as excinfo:
        design.validate(skip_footprint_check=True)

    assert "Invalid net registry key" in str(excinfo.value)
    assert "key/name mismatch" in str(excinfo.value)


def test_validate_rejects_connection_to_unplaced_component():
    design = Design("TestDesign")
    resistor = Resistor(1000)
    net = design.add_net("SIGNAL")
    net.connections.add(resistor.pins[1])
    design._pin_to_net[resistor.pins[1]] = net

    with pytest.raises(SchematicValidationError) as excinfo:
        design.validate(skip_footprint_check=True)

    assert "not owned by design" in str(excinfo.value)
