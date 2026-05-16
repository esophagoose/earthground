import pytest

import earthground.components as cmp
import earthground.library.connectors.connectors as conn
import earthground.layout as layout_lib
from earthground.exporters.kicad import KicadExporter
from earthground.assembly import Assembly, AssemblyValidationError
from earthground.library.connectors.fpc.te_2328702 import TE_2328702
from earthground.interfaces import (
    BoardToBoardInterface,
    NC,
    ConnectorInterface,
    InterfaceError,
    PinMap,
    Signal,
)
from earthground.schematic import Design


def placement_for(design, component):
    for refdes, candidate in design.components.items():
        if candidate is component:
            return design.layout.placement[refdes]
    raise AssertionError(f"Component not found in design: {component}")


def connector_with_numeric_mounting_pad(pin_count: int):
    connector = conn.standard_0_1_inch_header(pin_count=pin_count)
    pins = [cmp.Pin("MT0", 0, connector)]
    pins.extend(
        cmp.Pin(str(index), index, connector) for index in range(1, pin_count + 1)
    )
    connector.pins = cmp.PinContainer(pins)
    return connector


def test_connector_interface_generates_logical_pins_from_position_dict():
    interface = ConnectorInterface(
        "board_io",
        {
            1: Signal("GND_1", net_name="GND"),
            2: "IO0",
            3: NC,
            4: "IO1",
            5: Signal("P3V3", net_name="P3V3"),
            6: Signal("GND_2", net_name="GND"),
        },
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=6),
    )

    endpoint = interface.host()

    assert endpoint.pin("GND_1").index == 1
    assert endpoint.pin("IO0").index == 2
    assert endpoint.component.pins.by_name("NC_3").index == 3
    assert endpoint.pin("GND_2").index == 6
    assert endpoint.interface is interface


def test_signal_to_pin_returns_canonical_contact_position():
    interface = ConnectorInterface(
        "board_io",
        {
            1: Signal("GND_1", net_name="GND"),
            2: "IO0",
            3: NC,
            4: "IO1",
        },
    )

    assert interface.signal_to_pin("GND_1") == 1
    assert interface.signal_to_pin("IO0") == 2
    assert interface.signal_to_pin("IO1") == 4

    with pytest.raises(InterfaceError, match="Unknown signal: NC_3"):
        interface.signal_to_pin("NC_3")


def test_straight_mapping_uses_contact_keys_not_first_n_numeric_pads():
    interface = ConnectorInterface(
        "wide_board_io",
        {index: f"SIG{index}" for index in range(1, 45)},
        host_connector=lambda: connector_with_numeric_mounting_pad(44),
    )

    endpoint = interface.host()

    assert endpoint.component.pins.by_name("MT0").index == 0
    assert endpoint.pin("SIG1").index == 1
    assert endpoint.pin("SIG44").index == 44


def test_reversed_mapping_uses_contact_keys_not_first_n_numeric_pads():
    interface = ConnectorInterface(
        "board_link",
        {1: "A", 2: "B", 3: "C", 4: "D"},
        mate_connector=lambda: connector_with_numeric_mounting_pad(4),
        pin_map=PinMap.reversed(),
    )

    endpoint = interface.mate()

    assert endpoint.component.pins.by_name("MT0").index == 0
    assert endpoint.pin("A").index == 4
    assert endpoint.pin("B").index == 3
    assert endpoint.pin("C").index == 2
    assert endpoint.pin("D").index == 1


def test_missing_canonical_contact_pad_is_rejected():
    interface = ConnectorInterface(
        "wide_board_io",
        {index: f"SIG{index}" for index in range(1, 45)},
        host_connector=lambda: connector_with_numeric_mounting_pad(43),
    )

    with pytest.raises(InterfaceError, match="contact 44"):
        interface.host()


def test_default_connector_factories_create_fresh_components():
    interface = ConnectorInterface(
        "debug",
        {1: "SWDIO", 2: "SWCLK"},
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=2),
    )

    first = interface.host()
    second = interface.host()

    assert first.component is not second.component


def test_endpoint_requires_default_or_call_time_connector():
    interface = ConnectorInterface("debug", {1: "SWDIO"})

    with pytest.raises(InterfaceError, match="no default host connector"):
        interface.host()


def test_default_connectors_must_be_factories():
    with pytest.raises(InterfaceError, match="host_connector must be"):
        ConnectorInterface(
            "debug",
            {1: "SWDIO"},
            host_connector=conn.standard_0_1_inch_header(pin_count=1),
        )


def test_host_is_canonical_and_mate_uses_interface_pin_map():
    interface = ConnectorInterface(
        "board_link",
        {1: "A", 2: "B", 3: "C"},
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=3),
        mate_connector=lambda: conn.standard_0_1_inch_header(pin_count=3),
        pin_map=PinMap.reversed(),
    )

    host_endpoint = interface.host()
    mate_endpoint = interface.mate()

    assert host_endpoint.pin("A").index == 1
    assert host_endpoint.pin("B").index == 2
    assert host_endpoint.pin("C").index == 3
    assert mate_endpoint.pin("A").index == 3
    assert mate_endpoint.pin("B").index == 2
    assert mate_endpoint.pin("C").index == 1


def test_endpoint_generation_preserves_mechanical_pads():
    interface = ConnectorInterface(
        "fpc_io",
        {1: "A", 2: "B", 3: "C", 4: "D"},
        host_connector=lambda: TE_2328702(4),
    )

    endpoint = interface.host()

    assert endpoint.pin("A").index == 1
    assert endpoint.component.pins.by_name("MT1").index == "MT1"
    assert "MT1" not in endpoint.pins_by_signal


def test_kicad_export_maps_interface_pins_to_physical_pads():
    interface = ConnectorInterface(
        "debug",
        {1: "SWDIO", 2: "SWCLK"},
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=2),
    )
    design = Design("Debug")
    endpoint = interface.host()
    design.add_component(endpoint.component)
    endpoint.join_declared_nets()

    footprint = KicadExporter(design).parse_footprint(design, endpoint.component)
    nets_by_pad = {pad.number: pad.net.name for pad in footprint.pads}

    assert nets_by_pad == {"1": "SWDIO", "2": "SWCLK"}


def test_join_declared_nets_logs_error_for_missing_net(caplog):
    interface = ConnectorInterface(
        "debug",
        {1: Signal("SWDIO", net_name="DEBUG_SWDIO")},
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=1),
    )
    design = Design("Debug")
    endpoint = interface.host()
    design.add_component(endpoint.component)
    caplog.set_level("ERROR", logger="earthground.interfaces")

    endpoint.join_declared_nets()

    assert (
        "Declared net DEBUG_SWDIO does not exist before joining signal SWDIO"
        in caplog.text
    )
    assert "DEBUG_SWDIO" in design.nets


def test_custom_pin_map_must_cover_contacts_exactly():
    with pytest.raises(InterfaceError, match="cover interface positions exactly"):
        ConnectorInterface(
            "board_link",
            {1: "A", 2: "B", 3: "C"},
            mate_connector=lambda: conn.standard_0_1_inch_header(pin_count=3),
            pin_map=PinMap.custom({1: 1, 2: 2}),
        ).mate()


def test_duplicate_pin_names_are_rejected_but_shared_net_names_are_allowed():
    with pytest.raises(InterfaceError, match="duplicate pin names"):
        ConnectorInterface("bad_power", {1: "GND", 2: "GND"})

    interface = ConnectorInterface(
        "good_power",
        {
            1: Signal("GND_1", net_name="GND"),
            2: Signal("GND_2", net_name="GND"),
        },
    )

    assert [contact.signal.net_name for contact in interface.signal_contacts] == [
        "GND",
        "GND",
    ]


def test_assembly_validates_host_and_mate_endpoints():
    interface = ConnectorInterface(
        "board_link",
        {
            1: Signal("GND_1", net_name="GND"),
            2: "IO0",
            3: NC,
            4: Signal("P3V3", net_name="P3V3"),
        },
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=4),
        mate_connector=lambda: conn.standard_0_1_inch_header(pin_count=4),
        pin_map=PinMap.reversed(),
    )
    host = Design("Host")
    mate = Design("Mate")
    host_endpoint = interface.host()
    mate_endpoint = interface.mate()
    host.add_component(host_endpoint.component)
    mate.add_component(mate_endpoint.component)
    host_endpoint.join_declared_nets()
    mate_endpoint.join_declared_nets()

    assembly = Assembly("Product")
    assembly.add_board("host", host)
    assembly.add_board("mate", mate)
    assembly.add_interconnect("board_link", host_endpoint, mate_endpoint)

    assembly.validate()


def test_assembly_rejects_connected_no_connect_pins():
    interface = ConnectorInterface(
        "debug",
        {1: "SWDIO", 2: NC},
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=2),
        mate_connector=lambda: conn.standard_0_1_inch_header(pin_count=2),
    )
    host = Design("Host")
    mate = Design("Mate")
    host_endpoint = interface.host()
    mate_endpoint = interface.mate()
    host.add_component(host_endpoint.component)
    mate.add_component(mate_endpoint.component)
    host_endpoint.join_declared_nets()
    mate_endpoint.join_declared_nets()
    host.join_net(host_endpoint.component.pins.by_name("NC_2"), "SHOULD_NOT_CONNECT")

    assembly = Assembly("Product")
    assembly.add_board("host", host)
    assembly.add_board("mate", mate)
    assembly.add_interconnect("debug", host_endpoint, mate_endpoint)

    with pytest.raises(AssemblyValidationError, match="no-connect NC_2"):
        assembly.validate()


def test_board2board_interface_adds_host_and_mezzanine_sides():
    power = ConnectorInterface(
        "power",
        {
            1: Signal("GND_1", net_name="GND"),
            2: Signal("P3V3", net_name="P3V3"),
        },
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=2),
        mate_connector=lambda: conn.standard_0_1_inch_header(pin_count=2),
        pin_map=PinMap.reversed(),
    )
    debug = ConnectorInterface(
        "debug",
        {1: "SWDIO", 2: "SWCLK"},
        host_connector=lambda: conn.standard_0_1_inch_header(pin_count=2),
        mate_connector=lambda: conn.standard_0_1_inch_header(pin_count=2),
    )
    interface = BoardToBoardInterface(
        [power, debug],
        {
            "power": layout_lib.Position(x=0, y=0, angle=0),
            "debug": layout_lib.Position(x=20, y=0, angle=180),
        },
        outline=layout_lib.BoundingBox(x1=-5, y1=-4, x2=25, y2=4),
    )

    host = Design("Host")
    host_module = interface.add_to_host()
    host.add_module(host_module)
    host.join_net(host_module.port["GND"], "GND")
    host.join_net(host_module.port["P3V3"], "P3V3")
    host.join_net(host_module.port["SWDIO"], "SWDIO")
    host.join_net(host_module.port["SWCLK"], "SWCLK")
    host.layout.placement["B2BH1"] = layout_lib.Placement(
        position=layout_lib.Position(x=100, y=50, angle=90),
        layer=layout_lib.Layer.TOP,
    )
    host_endpoints = host_module.connector_endpoints

    assert set(host_endpoints) == {"power", "debug"}
    assert host_endpoints["power"].role == "host"
    assert host_endpoints["power"].pin("GND_1").index == 1
    assert host_module.pin_to_net[host_endpoints["power"].pin("GND_1")].name == "GND"
    assert host_module.pin_to_net[host_endpoints["power"].pin("P3V3")].name == "P3V3"
    flattened_layout = host.layout.flatten()
    assert flattened_layout["B2BH1_J2"][0].component == layout_lib.Position(
        x=100, y=70, angle=270
    )
    assert flattened_layout["B2BH1_J2"][0].layer == layout_lib.Layer.TOP
    assert len(host_module.layout.silk) == 4
    assert host.layout.flatten_silk()[0] == layout_lib.SilkLine(
        start=layout_lib.Position(x=104, y=45, angle=90),
        end=layout_lib.Position(x=104, y=75, angle=90),
    )

    exporter = KicadExporter(host)
    exporter.draw_silkscreen_lines()
    assert len(exporter.board.graphicItems) == 4
    assert exporter.board.graphicItems[0].layer == "F.SilkS"

    mezzanine = Design("Mezzanine")
    mate_module = interface.add_to_mezzanine()
    mezzanine.add_module(mate_module)
    mate_endpoints = mate_module.connector_endpoints

    assert mate_endpoints["power"].role == "mate"
    assert mate_endpoints["power"].pin("GND_1").index == 2
    assert (
        placement_for(mate_module, mate_endpoints["power"].component).layer
        == layout_lib.Layer.BOTTOM
    )
