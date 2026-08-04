"""Non-mutating, hierarchy-aware electrical analysis helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
import itertools
from typing import Optional

import earthground.components as cmp
import earthground.layout as layout_lib
import earthground.standard_values as sv


@dataclass(frozen=True)
class ResolvedComponent:
    refdes: str
    component: cmp.Component
    placement: Optional[layout_lib.ComponentLayout]
    fallback_placement: Optional[layout_lib.ComponentLayout] = None
    placement_provenance: layout_lib.PlacementProvenance = (
        layout_lib.PlacementProvenance.FALLBACK
    )


@dataclass(frozen=True)
class ResolvedNet:
    name: str
    connections: frozenset[cmp.Pin]
    voltage: Optional[sv.ValueBounds]
    voltage_conflict: bool = False
    power_voltage: Optional[sv.ValueBounds] = None
    externally_driven: bool = False
    voltage_method: Optional[str] = None


def group_logical_pins(pins) -> tuple[tuple[cmp.Pin, ...], ...]:
    """Group physical package pins by component-local logical pin name."""

    groups: dict[tuple[object, str], list[cmp.Pin]] = {}
    for pin in pins:
        groups.setdefault((pin.parent, pin.name), []).append(pin)
    return tuple(tuple(group) for group in groups.values())


def _single_logical_source_voltage(pins) -> Optional[sv.ValueBounds]:
    groups = group_logical_pins(pins)
    if len(groups) != 1:
        return None
    voltages = [
        pin.erc.voltage_operating
        for pin in groups[0]
        if pin.erc.voltage_operating is not None
    ]
    if not voltages or any(voltage != voltages[0] for voltage in voltages[1:]):
        return None
    return voltages[0]


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
            power_voltage = None if conflict or not values else values[0]
            if name == design.ground:
                power_voltage = sv.volts(0, typ=0, max=0)
                conflict = False
            if power_voltage is None and not conflict:
                power_sources = [
                    pin
                    for pin in pins
                    if _active_pin(pin)
                    and pin.erc.power_role is cmp.PowerRole.OUTPUT
                    and pin.erc.voltage_operating is not None
                ]
                power_voltage = _single_logical_source_voltage(power_sources)

            externally_driven = name in external
            voltage = power_voltage
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
                    voltage = _single_logical_source_voltage(sources)
            self.nets[name] = ResolvedNet(
                name=name,
                connections=frozenset(pins),
                voltage=voltage,
                voltage_conflict=conflict,
                power_voltage=power_voltage,
                externally_driven=externally_driven,
                voltage_method="declared or driven" if voltage is not None else None,
            )

        self._infer_resistive_voltages()

        self.components = tuple(
            ResolvedComponent(
                refdes,
                item.component,
                (
                    item.layout
                    if item.provenance is layout_lib.PlacementProvenance.EXPLICIT
                    else None
                ),
                item.layout,
                item.provenance,
            )
            for refdes, item in design.layout.flatten_with_provenance(
                warn_on_fallback=False
            ).items()
            if not item.component.virtual
        )
        self._component_lookup = {item.component: item for item in self.components}

    def net_for_pin(self, pin: cmp.Pin) -> Optional[ResolvedNet]:
        name = self._pin_to_name.get(pin)
        return None if name is None else self.nets.get(name)

    def component_for(self, component: cmp.Component) -> Optional[ResolvedComponent]:
        return self._component_lookup.get(component)

    def voltage_for_pin(self, pin: cmp.Pin) -> Optional[sv.ValueBounds]:
        net = self.net_for_pin(pin)
        if net is not None and not net.voltage_conflict:
            return net.voltage
        spec = pin.spec
        if not isinstance(spec, cmp.DigitalPinSpec):
            return None
        internal = spec.internal
        target_name = None
        method = None
        if internal.pull_up is True and internal.pull_up_to:
            target_name = internal.pull_up_to
            method = "internal pull-up"
        elif internal.pull_down is True and internal.pull_down_to:
            target_name = internal.pull_down_to
            method = "internal pull-down"
        if target_name is None:
            return None
        try:
            target_pin = pin.parent.pins.by_name(target_name)
        except ValueError:
            return None
        target = self.net_for_pin(target_pin)
        if target is None or target.voltage_conflict or target.voltage is None:
            return None
        source = tuple(
            dict.fromkeys(target.voltage.source + ((internal.source or method),))
        )
        return sv.ValueBounds(
            target.voltage.units,
            target.voltage.min,
            typ=target.voltage.typ,
            max=target.voltage.max,
            source=source,
        )

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

    def _infer_resistive_voltages(self) -> None:
        for _ in range(len(self.nets)):
            changed = False
            for name, net in tuple(self.nets.items()):
                if (
                    net.voltage is not None
                    or net.voltage_conflict
                    or net.externally_driven
                ):
                    continue
                if not _is_high_impedance_signal(net):
                    continue
                branches = [
                    (resistor, other.voltage)
                    for resistor, other in self.resistor_branches(net)
                    if other is not None
                    and not other.voltage_conflict
                    and other.voltage is not None
                ]
                voltage = _solve_resistor_node(branches)
                if voltage is None:
                    continue
                self.nets[name] = replace(
                    net,
                    voltage=voltage,
                    voltage_method="resistive DC inference",
                )
                changed = True
            if not changed:
                break


def _active_pin(pin: cmp.Pin) -> bool:
    parent = pin.parent
    return isinstance(parent, cmp.Component) and not parent.virtual and not parent.dnp


def _is_high_impedance_signal(net: ResolvedNet) -> bool:
    for pin in net.connections:
        parent = pin.parent
        if not _active_pin(pin) or isinstance(parent, cmp.Resistor):
            continue
        if isinstance(parent, cmp.Capacitor):
            continue
        if pin.erc.power_role is not None:
            return False
        directions = pin.erc.directions
        if not directions or not directions.issubset({cmp.PinDirection.INPUT}):
            return False
    return True


def _resistance_range(resistor: cmp.Resistor) -> tuple[Decimal, Decimal]:
    nominal = resistor.value.value
    tolerance = resistor.tolerance
    if tolerance is None or tolerance.min is None or tolerance.max is None:
        return nominal, nominal
    return nominal * (Decimal(1) + tolerance.min), nominal * (
        Decimal(1) + tolerance.max
    )


def _solve_resistor_node(branches) -> Optional[sv.ValueBounds]:
    if not branches:
        return None
    if any(voltage.min is None or voltage.max is None for _, voltage in branches):
        return None
    corners = []
    ranges = [
        (
            _resistance_range(resistor),
            (voltage.min, voltage.max),
        )
        for resistor, voltage in branches
    ]
    choices = [
        tuple(itertools.product(resistance, voltage)) for resistance, voltage in ranges
    ]
    for combination in itertools.product(*choices):
        conductance = sum(
            (Decimal(1) / resistance for resistance, _ in combination), Decimal(0)
        )
        if conductance <= 0:
            return None
        corners.append(
            sum(
                (value / resistance for resistance, value in combination),
                Decimal(0),
            )
            / conductance
        )
    typical_terms = []
    for resistor, voltage in branches:
        if voltage.typ is None:
            typical_terms = []
            break
        typical_terms.append((resistor.value.value, voltage.typ))
    typical = None
    if typical_terms:
        g_typ = sum(
            (Decimal(1) / resistance for resistance, _ in typical_terms), Decimal(0)
        )
        typical = (
            sum((value / resistance for resistance, value in typical_terms), Decimal(0))
            / g_typ
        )
    sources = tuple(
        dict.fromkeys(
            source for resistor, voltage in branches for source in voltage.source
        )
    )
    return sv.volts(min(corners), typ=typical, max=max(corners), source=sources)


def _module_entries(design):
    by_symbol = {module.port.symbol: module for module in design.modules}
    for cid, component in design.components.items():
        module = by_symbol.get(component)
        if module is not None:
            yield cid, module
