"""Non-mutating, hierarchy-aware electrical analysis helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import earthground.components as cmp
import earthground.layout as layout_lib
import earthground.standard_values as sv


@dataclass(frozen=True)
class ResolvedComponent:
    refdes: str
    component: cmp.Component
    placement: Optional[layout_lib.ComponentLayout]


@dataclass(frozen=True)
class ResolvedNet:
    name: str
    connections: frozenset[cmp.Pin]
    voltage: Optional[sv.ValueBounds]
    voltage_conflict: bool = False


class DesignAnalysis:
    """A read-only flattened view of a Design and its module hierarchy."""

    def __init__(self, design):
        self.design = design
        resolved = design._resolved_net_connections()
        self._pin_to_name = {
            pin: name for name, pins in resolved.items() for pin in pins
        }
        declarations: dict[str, list[sv.ValueBounds]] = {}
        external: dict[str, list[Optional[sv.ValueBounds]]] = {}
        for page in design.iter_designs():
            for name, value in page._declared_rails.items():
                declarations.setdefault(name, []).append(value)
            for name, value in page._external_drives.items():
                external.setdefault(name, []).append(value)

        self.nets: dict[str, ResolvedNet] = {}
        for name, pins in resolved.items():
            values = declarations.get(name, [])
            conflict = bool(values and any(value != values[0] for value in values[1:]))
            voltage = None if conflict or not values else values[0]
            if name == design.ground:
                voltage = sv.volts(0, typ=0, max=0)
                conflict = False
            if voltage is None and not conflict:
                driven = [
                    value for value in external.get(name, []) if value is not None
                ]
                if driven and all(value == driven[0] for value in driven[1:]):
                    voltage = driven[0]
                else:
                    sources = [
                        pin
                        for pin in pins
                        if _active_pin(pin)
                        and (
                            pin.erc.power_role is cmp.PowerRole.OUTPUT
                            or bool(
                                pin.erc.directions
                                & {
                                    cmp.PinDirection.OUTPUT,
                                    cmp.PinDirection.BIDIRECTIONAL,
                                }
                            )
                        )
                        and pin.erc.voltage_operating is not None
                    ]
                    if len(sources) == 1:
                        voltage = sources[0].erc.voltage_operating
            self.nets[name] = ResolvedNet(
                name=name,
                connections=frozenset(pins),
                voltage=voltage,
                voltage_conflict=conflict,
            )

        self.components = tuple(_resolved_components(design))
        self._component_lookup = {item.component: item for item in self.components}

    def net_for_pin(self, pin: cmp.Pin) -> Optional[ResolvedNet]:
        name = self._pin_to_name.get(pin)
        return None if name is None else self.nets.get(name)

    def component_for(self, component: cmp.Component) -> Optional[ResolvedComponent]:
        return self._component_lookup.get(component)

    def active_connections(self, net: ResolvedNet) -> tuple[cmp.Pin, ...]:
        return tuple(pin for pin in net.connections if _active_pin(pin))

    def resistor_branches(self, net: ResolvedNet):
        """Yield active resistors attached to net and their opposite resolved net."""
        seen = set()
        for pin in net.connections:
            resistor = pin.parent
            if (
                not _active_pin(pin)
                or not isinstance(resistor, cmp.Resistor)
                or resistor in seen
            ):
                continue
            seen.add(resistor)
            other = next(
                (candidate for candidate in resistor.pins if candidate is not pin), None
            )
            if other is not None:
                yield resistor, self.net_for_pin(other)


def _active_pin(pin: cmp.Pin) -> bool:
    parent = pin.parent
    return isinstance(parent, cmp.Component) and not parent.virtual and not parent.dnp


def _module_entries(design):
    by_symbol = {module.port.symbol: module for module in design.modules}
    for cid, component in design.components.items():
        module = by_symbol.get(component)
        if module is not None:
            yield cid, module


def _resolved_components(
    design,
    *,
    prefix: str = "",
    parent_layout: Optional[layout_lib.ComponentLayout] = None,
    parent_explicit: bool = True,
):
    modules = {module.port.symbol: module for module in design.modules}
    for cid, component in design.components.items():
        refdes = f"{prefix}_{cid}" if prefix else cid
        explicit = parent_explicit and cid in design.layout.placement
        local_layout = (
            design.layout.get_placement(cid) if cid in design.layout.placement else None
        )
        if local_layout is not None and parent_layout is not None:
            component_position = layout_lib.transform_position(
                local_layout.component, parent_layout.component
            )
            id_position = layout_lib.rotate_position(
                local_layout.id, parent_layout.component.angle
            )
            local_layout = layout_lib.ComponentLayout(
                id=id_position,
                id_orientation=local_layout.id_orientation,
                component=component_position,
                layer=layout_lib.combine_layer(parent_layout.layer, local_layout.layer),
            )
        if not explicit:
            local_layout = None

        module = modules.get(component)
        if module is not None:
            yield from _resolved_components(
                module,
                prefix=refdes,
                parent_layout=local_layout,
                parent_explicit=explicit,
            )
        elif not component.virtual:
            yield ResolvedComponent(refdes, component, local_layout)
