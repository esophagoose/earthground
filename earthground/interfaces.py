from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Mapping
from typing import Any, Literal, Optional

import earthground.components as cmp
import earthground.layout as layout_lib
import earthground.footprint_types as ft
import earthground.schematic as sch_lib

log = logging.getLogger(__name__)

ContactPosition = int | str
ContactValue = Any
EndpointRole = Literal["host", "mate"]
ConnectorFactory = Callable[[], cmp.Component]
ConnectorSpec = cmp.Component | ConnectorFactory

__all__ = [
    "NC",
    "ConnectorEndpoint",
    "ConnectorInterface",
    "Contact",
    "BoardToBoardInterface",
    "InterfaceError",
    "PinMap",
    "Signal",
]


class InterfaceError(ValueError):
    pass


class _NoConnect:
    def __repr__(self) -> str:
        return "NC"


NC = _NoConnect()


@dataclasses.dataclass(frozen=True)
class Signal:
    name: str
    net_name: Optional[str] = None
    required: bool = True
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise InterfaceError("Signal name cannot be empty")
        if self.net_name is None:
            object.__setattr__(self, "net_name", self.name)


@dataclasses.dataclass(frozen=True)
class Contact:
    position: ContactPosition
    signal: Optional[Signal] = None

    @property
    def is_no_connect(self) -> bool:
        return self.signal is None

    @property
    def pin_name(self) -> str:
        if self.signal is None:
            return f"NC_{self.position}"
        return self.signal.name


class PinMap:
    def __init__(
        self,
        mode: Literal["straight", "reversed", "custom"],
        mapping: Optional[Mapping[ContactPosition, ContactPosition]] = None,
    ):
        self.mode = mode
        self.mapping = dict(mapping or {})

    @classmethod
    def straight(cls) -> "PinMap":
        return cls("straight")

    @classmethod
    def reversed(cls) -> "PinMap":
        return cls("reversed")

    @classmethod
    def custom(cls, mapping: Mapping[ContactPosition, ContactPosition]) -> "PinMap":
        return cls("custom", mapping)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PinMap):
            return False
        return self.mode == other.mode and self.mapping == other.mapping

    def resolve(
        self, interface: "ConnectorInterface", component: cmp.Component
    ) -> dict[ContactPosition, ContactPosition]:
        if self.mode == "custom":
            return self._resolve_custom(interface, component)

        positions = interface.positions
        pads = positions
        if self.mode == "reversed":
            pads = list(reversed(positions))
        return {
            position: _component_index_for(component, pad)
            for position, pad in zip(positions, pads)
        }

    def _resolve_custom(
        self, interface: "ConnectorInterface", component: cmp.Component
    ) -> dict[ContactPosition, ContactPosition]:
        positions = set(interface.positions)
        mapped_positions = set(self.mapping)
        if mapped_positions != positions:
            missing = sorted(positions - mapped_positions, key=_position_sort_key)
            extra = sorted(mapped_positions - positions, key=_position_sort_key)
            raise InterfaceError(
                f"Custom pin map must cover interface positions exactly. "
                f"Missing: {missing}; extra: {extra}"
            )

        resolved_pads = [
            _component_index_for(component, pad) for pad in self.mapping.values()
        ]
        if len(set(resolved_pads)) != len(resolved_pads):
            raise InterfaceError(
                "Custom pin map cannot map multiple contacts to one pad"
            )

        return dict(zip(self.mapping, resolved_pads))


@dataclasses.dataclass(frozen=True)
class ConnectorEndpoint:
    interface: "ConnectorInterface"
    role: EndpointRole
    component: cmp.Component
    pin_map: dict[ContactPosition, ContactPosition]
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def pin(self, signal_name: str) -> cmp.Pin:
        return self.component.pins.by_name(signal_name)

    @property
    def pins_by_signal(self) -> dict[str, cmp.Pin]:
        pins = {}
        for contact in self.interface.signal_contacts:
            pins[contact.signal.name] = self.component.pins.by_name(contact.pin_name)
        return pins

    @property
    def no_connect_pins(self) -> list[cmp.Pin]:
        pins = []
        for contact in self.interface.no_connect_contacts:
            pins.append(self.component.pins.by_name(contact.pin_name))
        return pins

    def join_declared_nets(self, design=None) -> None:
        design = design or self.component.parent
        if design is None:
            raise InterfaceError("Endpoint component must be added to a design first")
        for contact in self.interface.signal_contacts:
            signal = contact.signal
            if signal.net_name not in design.nets:
                log.error(
                    "Declared net %s does not exist before joining signal %s on %s",
                    signal.net_name,
                    signal.name,
                    self.component,
                )
            design.join_net(self.component.pins.by_name(signal.name), signal.net_name)


class ConnectorInterface:
    def __init__(
        self,
        name: str,
        contacts: Mapping[ContactPosition, ContactValue],
        host_connector: Optional[ConnectorFactory] = None,
        mate_connector: Optional[ConnectorFactory] = None,
        pin_map: Optional[PinMap] = None,
    ):
        if not name:
            raise InterfaceError("ConnectorInterface name cannot be empty")
        if not contacts:
            raise InterfaceError("ConnectorInterface contacts cannot be empty")
        if host_connector is not None and not callable(host_connector):
            raise InterfaceError("host_connector must be a connector factory")
        if mate_connector is not None and not callable(mate_connector):
            raise InterfaceError("mate_connector must be a connector factory")
        self.name = name
        self.contacts = {
            position: _normalize_contact(position, value)
            for position, value in sorted(
                contacts.items(), key=lambda item: _position_sort_key(item[0])
            )
        }
        self.host_connector = host_connector
        self.mate_connector = mate_connector
        self.pin_map = pin_map or PinMap.straight()
        self._validate()

    @property
    def positions(self) -> list[ContactPosition]:
        return list(self.contacts.keys())

    @property
    def signal_contacts(self) -> list[Contact]:
        return [contact for contact in self.contacts.values() if contact.signal]

    @property
    def no_connect_contacts(self) -> list[Contact]:
        return [contact for contact in self.contacts.values() if contact.is_no_connect]

    def signal_to_pin(self, signal_name: str) -> ContactPosition:
        for position, contact in self.contacts.items():
            if contact.signal is not None and contact.signal.name == signal_name:
                return position
        raise InterfaceError(f"Unknown signal: {signal_name}")

    def host(
        self,
        connector: Optional[ConnectorSpec] = None,
        **metadata: Any,
    ) -> ConnectorEndpoint:
        connector = connector or self.host_connector
        return self._endpoint("host", connector, PinMap.straight(), metadata)

    def mate(
        self,
        connector: Optional[ConnectorSpec] = None,
        **metadata: Any,
    ) -> ConnectorEndpoint:
        connector = connector or self.mate_connector
        return self._endpoint("mate", connector, self.pin_map, metadata)

    def _endpoint(
        self,
        role: EndpointRole,
        connector: Optional[ConnectorSpec],
        pin_map: PinMap,
        metadata: Mapping[str, Any],
    ) -> ConnectorEndpoint:
        if connector is None:
            raise InterfaceError(
                f"ConnectorInterface {self.name} has no default {role} connector"
            )
        component = connector() if callable(connector) else connector
        if not isinstance(component, cmp.Component):
            raise InterfaceError(
                f"Connector factory must return Component, got {type(component)}"
            )
        resolved = pin_map.resolve(self, component)
        _apply_interface_pins(component, self, resolved)
        return ConnectorEndpoint(
            interface=self,
            role=role,
            component=component,
            pin_map=resolved,
            metadata=dict(metadata),
        )

    def _validate(self) -> None:
        pin_names = [contact.pin_name for contact in self.contacts.values()]
        if len(pin_names) != len(set(pin_names)):
            raise InterfaceError(
                "ConnectorInterface generated duplicate pin names; use unique "
                "Signal names and shared net_name for repeated rails"
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConnectorInterface):
            return False
        return (
            self.name == other.name
            and self.contacts == other.contacts
            and self.pin_map == other.pin_map
        )


class BoardToBoardInterface:
    """Higher-level helper for multi-connector board-to-board interfaces."""

    def __init__(
        self,
        connectors: list[ConnectorInterface],
        placement: Mapping[str, layout_lib.Position],
        outline: ft.BoundingBox,
    ) -> None:
        if not connectors:
            raise InterfaceError("BoardToBoardInterface connectors cannot be empty")
        connector_names = [connector.name for connector in connectors]
        if len(connector_names) != len(set(connector_names)):
            raise InterfaceError(
                "BoardToBoardInterface connector interface names must be unique"
            )
        placement_names = set(placement)
        expected_names = set(connector_names)
        if placement_names != expected_names:
            missing = sorted(expected_names - placement_names)
            extra = sorted(placement_names - expected_names)
            raise InterfaceError(
                "BoardToBoardInterface placement must cover connector names exactly. "
                f"Missing: {missing}; extra: {extra}"
            )
        self.connectors = connectors
        self.placement = dict(placement)
        self.outline = outline

    def add_to_host(self) -> sch_lib.Design:
        return self._build_module(
            name="BoardToBoardHost",
            short_name="B2BH",
            role="host",
            layer=layout_lib.Layer.TOP,
        )

    def add_to_mezzanine(self) -> sch_lib.Design:
        return self._build_module(
            name="BoardToBoardMezzanine",
            short_name="B2BM",
            role="mate",
            layer=layout_lib.Layer.BOTTOM,
        )

    def _build_module(
        self, *, name: str, short_name: str, role: EndpointRole, layer: layout_lib.Layer
    ) -> sch_lib.Design:
        net_names = self._declared_net_names()
        design = sch_lib.Design(name, short_name, ports=net_names)
        for net_name in net_names:
            if net_name not in design.nets:
                design.add_net(net_name)
            design.join_net(design.port[net_name], net_name)
        endpoints: dict[str, ConnectorEndpoint] = {}
        for connector in self.connectors:
            endpoint = connector.host() if role == "host" else connector.mate()
            design.add_component(endpoint.component)
            endpoint.join_declared_nets(design)
            refdes = _component_key(design, endpoint.component)
            design.layout.placement[refdes] = layout_lib.Placement(
                position=self.placement[connector.name],
                id=None,
                layer=layer,
            )
            endpoints[connector.name] = endpoint
        self._add_outline(design, layer)
        design.connector_endpoints = endpoints
        return design

    def _declared_net_names(self) -> list[str]:
        net_names = []
        for connector in self.connectors:
            for contact in connector.signal_contacts:
                net_name = contact.signal.net_name
                if net_name not in net_names:
                    net_names.append(net_name)
        return net_names

    def _add_outline(self, design: sch_lib.Design, layer: layout_lib.Layer) -> None:
        corners = [
            layout_lib.Position(self.outline.x1, self.outline.y1, 0),
            layout_lib.Position(self.outline.x2, self.outline.y1, 0),
            layout_lib.Position(self.outline.x2, self.outline.y2, 0),
            layout_lib.Position(self.outline.x1, self.outline.y2, 0),
        ]
        for start, end in zip(corners, corners[1:] + corners[:1]):
            design.layout.silk.append(
                layout_lib.SilkLine(start=start, end=end, layer=layer)
            )


def _normalize_contact(position: ContactPosition, value: ContactValue) -> Contact:
    if value is NC:
        return Contact(position=position)
    if isinstance(value, Signal):
        return Contact(position=position, signal=value)
    if isinstance(value, str):
        return Contact(position=position, signal=Signal(value))
    raise InterfaceError(f"Invalid contact value at {position}: {value!r}")


def _component_indices(component: cmp.Component) -> set[ContactPosition]:
    footprint_indices = set(getattr(component.footprint, "pads", {}) or {})
    component_indices = set(component.pins.indicies)
    return footprint_indices | component_indices


def _component_index_for(
    component: cmp.Component, requested_index: ContactPosition
) -> ContactPosition:
    indices = _component_indices(component)
    if requested_index in indices:
        return requested_index

    matches = [
        index
        for index in indices
        if _is_numeric_position(index)
        and _is_numeric_position(requested_index)
        and str(index) == str(requested_index)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise InterfaceError(
            f"Connector {component.name} has ambiguous equivalent indices for "
            f"{requested_index}: {sorted(matches, key=_position_sort_key)}"
        )
    raise InterfaceError(
        f"Connector {component.name} has no pad/index for interface contact "
        f"{requested_index}"
    )


def _apply_interface_pins(
    component: cmp.Component,
    interface: ConnectorInterface,
    pin_map: Mapping[ContactPosition, ContactPosition],
) -> None:
    original = component.pins
    replacement_names = {
        pad_index: interface.contacts[contact_position].pin_name
        for contact_position, pad_index in pin_map.items()
    }
    all_indices = sorted(
        set(original.indicies) | set(replacement_names), key=_position_sort_key
    )
    pins = []
    for index in all_indices:
        name = replacement_names.get(index)
        if name is None:
            name = original.indicies[index].name
        pins.append(cmp.Pin(name, index, component))
    component.pins = cmp.PinContainer(pins)


def _component_key(design, component: cmp.Component) -> str:
    for refdes, candidate in design.components.items():
        if candidate is component:
            return refdes
    raise InterfaceError(f"Component {component} is not in design {design.name}")


def _is_numeric_position(position: ContactPosition) -> bool:
    try:
        int(position)
    except (TypeError, ValueError):
        return False
    return True


def _position_sort_key(position: ContactPosition) -> tuple[int, Any]:
    if _is_numeric_position(position):
        return (0, int(position))
    return (1, str(position))
