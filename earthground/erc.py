from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import earthground.components as cmp
import earthground.standard_values as sv
from earthground.analysis import DesignAnalysis, ResolvedNet

if TYPE_CHECKING:
    from earthground.schematic import Design


@dataclass(frozen=True)
class ElectricalCheck:
    rule_id: str
    status: sv.CheckStatus
    message: str
    design: str
    net: Optional[str] = None
    pin: Optional[str] = None
    sources: tuple[str, ...] = ()

    def __str__(self):
        location = self.design
        if self.net:
            location += f":{self.net}"
        if self.pin:
            location += f":{self.pin}"
        source = f" [sources: {', '.join(self.sources)}]" if self.sources else ""
        return (
            f"{self.rule_id} {self.status.value} at {location}: "
            f"{self.message}{source}"
        )


@dataclass(frozen=True)
class ElectricalReport:
    checks: tuple[ElectricalCheck, ...]

    @property
    def passes(self):
        return tuple(c for c in self.checks if c.status is sv.CheckStatus.PASS)

    @property
    def failures(self):
        return tuple(c for c in self.checks if c.status is sv.CheckStatus.FAIL)

    @property
    def unknowns(self):
        return tuple(c for c in self.checks if c.status is sv.CheckStatus.UNKNOWN)

    @property
    def is_valid(self):
        return not self.failures and not self.unknowns


def _active_pin(pin: cmp.Pin) -> bool:
    parent = pin.parent
    return isinstance(parent, cmp.Component) and not parent.virtual and not parent.dnp


def _is_output_capable(characteristics: cmp.ErcCharacteristics) -> bool:
    return characteristics.power_role is cmp.PowerRole.OUTPUT or bool(
        characteristics.directions
        & {cmp.PinDirection.OUTPUT, cmp.PinDirection.BIDIRECTIONAL}
    )


def _is_unconditional_driver(characteristics: cmp.ErcCharacteristics) -> bool:
    if characteristics.power_role is cmp.PowerRole.OUTPUT:
        return True
    conditional_styles = {cmp.DriveStyle.OPEN_DRAIN, cmp.DriveStyle.TRI_STATE}
    return characteristics.directions == frozenset(
        (cmp.PinDirection.OUTPUT,)
    ) and characteristics.drive_styles.isdisjoint(conditional_styles)


def _drives_without_bias(characteristics: cmp.ErcCharacteristics) -> bool:
    return (
        _is_output_capable(characteristics)
        and cmp.DriveStyle.OPEN_DRAIN not in characteristics.drive_styles
    )


def _pin_label(pin: cmp.Pin) -> str:
    parent = pin.parent
    if isinstance(parent, cmp.Component):
        return f"{parent.refdes}.{pin.index}({pin.name})"
    return f"{pin.index}({pin.name})"


def _sources(*bounds) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            source for bound in bounds if bound is not None for source in bound.source
        )
    )


def _resolved_power_voltage(net: ResolvedNet) -> Optional[sv.ValueBounds]:
    if net.voltage_conflict:
        return None
    return net.power_voltage


def _resolved_net_voltage(net: ResolvedNet) -> Optional[sv.ValueBounds]:
    return None if net.voltage_conflict else net.voltage


def _resistive_bias(
    analysis: DesignAnalysis,
    net: ResolvedNet,
    *,
    polarity: str = "any",
) -> tuple[bool, Optional[sv.ValueBounds]]:
    for _, other_net in analysis.resistor_branches(net):
        if other_net is None:
            continue
        voltage = _resolved_power_voltage(other_net)
        if voltage is None:
            continue
        if polarity == "positive" and (
            voltage.min is None or voltage.min <= Decimal(0)
        ):
            continue
        if polarity == "non_positive" and (
            voltage.max is None or voltage.max > Decimal(0)
        ):
            continue
        return True, voltage
    return False, None


def _has_internal_bias(pin: cmp.Pin) -> bool:
    spec = pin.spec
    return isinstance(spec, cmp.DigitalPinSpec) and (
        spec.internal.pull_up is True or spec.internal.pull_down is True
    )


def _check_local(
    design: "Design", design_path: str, analysis: DesignAnalysis
) -> list[ElectricalCheck]:
    checks = []
    active_pins = [
        pin
        for component in design.components.values()
        if not component.virtual and not component.dnp
        for pin in component.pins
    ]

    def add(rule, status, message, pin=None, net=None, bounds=()):
        checks.append(
            ElectricalCheck(
                rule,
                status,
                message,
                design_path,
                net=None if net is None else net.name,
                pin=None if pin is None else _pin_label(pin),
                sources=_sources(*bounds),
            )
        )

    # E1: supply compatibility.
    for pin in active_pins:
        characteristics = pin.erc
        if characteristics.power_role not in {
            cmp.PowerRole.INPUT,
            cmp.PowerRole.GROUND,
        }:
            continue
        net = analysis.net_for_pin(pin)
        rail = None if net is None else _resolved_power_voltage(net)
        if characteristics.voltage_operating is None or rail is None:
            add(
                "E1",
                sv.CheckStatus.UNKNOWN,
                "power input operating range or rail voltage is unresolved",
                pin,
                net,
                (characteristics.voltage_operating, rail),
            )
            continue
        status = characteristics.voltage_operating.covers(rail)
        add(
            "E1",
            status,
            (
                "power input operating range covers rail"
                if status is sv.CheckStatus.PASS
                else "power input operating range does not conclusively cover rail"
            ),
            pin,
            net,
            (characteristics.voltage_operating, rail),
        )

    # E3: floating inputs.
    for pin in active_pins:
        if pin.erc.directions != frozenset((cmp.PinDirection.INPUT,)):
            continue
        net = analysis.net_for_pin(pin)
        internal_bias = _has_internal_bias(pin)
        if net is None:
            add(
                "E3",
                sv.CheckStatus.PASS if internal_bias else sv.CheckStatus.FAIL,
                (
                    "unconnected input has a declared internal pull-up or pull-down"
                    if internal_bias
                    else "input is unconnected"
                ),
                pin,
            )
            continue
        connections = analysis.active_connections(net)
        has_driver = any(
            other is not pin and _drives_without_bias(other.erc)
            for other in connections
        )
        has_bias, _ = _resistive_bias(analysis, net)
        has_declared_source = net.power_voltage is not None or net.externally_driven
        driven = has_driver or has_bias or has_declared_source or internal_bias
        add(
            "E3",
            sv.CheckStatus.PASS if driven else sv.CheckStatus.FAIL,
            (
                "input has a modeled driver or bias"
                if driven
                else "input net has no modeled driver, external drive, rail, or bias"
            ),
            pin,
            net,
        )

    # E4: no-connect pins.
    for pin in active_pins:
        if pin.erc.connection is not cmp.ConnectionPolicy.MUST_NOT_CONNECT:
            continue
        net = analysis.net_for_pin(pin)
        add(
            "E4",
            sv.CheckStatus.PASS if net is None else sv.CheckStatus.FAIL,
            (
                "no-connect pin is unconnected"
                if net is None
                else "no-connect pin is connected"
            ),
            pin,
            net,
        )

    # E6: absolute maximum voltage.
    for pin in active_pins:
        abs_max = pin.erc.voltage_abs_max
        if abs_max is None:
            continue
        net = analysis.net_for_pin(pin)
        voltage = None if net is None else _resolved_net_voltage(net)
        if voltage is None:
            add(
                "E6",
                sv.CheckStatus.UNKNOWN,
                "net voltage is unresolved for absolute-maximum check",
                pin,
                net,
                (abs_max,),
            )
            continue
        status = abs_max.covers(voltage)
        add(
            "E6",
            status,
            (
                "absolute maximum covers resolved net voltage"
                if status is sv.CheckStatus.PASS
                else "absolute maximum does not conclusively cover resolved net voltage"
            ),
            pin,
            net,
            (abs_max, voltage),
        )

    # E7: ambient temperature.
    for component in design.components.values():
        if component.virtual or component.dnp or "ta" not in component.recommended:
            continue
        rating = component.recommended["ta"]
        if design._ambient is None:
            add(
                "E7",
                sv.CheckStatus.UNKNOWN,
                f"{component.refdes} has an ambient rating but design ambient is undeclared",
                bounds=(rating,),
            )
            continue
        status = rating.covers(design._ambient)
        add(
            "E7",
            status,
            (
                f"{component.refdes} ambient rating covers design range"
                if status is sv.CheckStatus.PASS
                else f"{component.refdes} ambient rating does not conclusively cover design range"
            ),
            bounds=(rating, design._ambient),
        )
    return checks


def _check_global_nets(
    analysis: DesignAnalysis, design_path: str
) -> list[ElectricalCheck]:
    checks = []

    def add(rule, status, message, net, bounds=()):
        checks.append(
            ElectricalCheck(
                rule,
                status,
                message,
                design_path,
                net=net.name,
                sources=_sources(*bounds),
            )
        )

    # E2: unconditional driver contention on each flattened physical net.
    for net in analysis.nets.values():
        drivers = [
            pin
            for pin in analysis.active_connections(net)
            if _is_unconditional_driver(pin.erc)
        ]
        if not drivers:
            continue
        add(
            "E2",
            sv.CheckStatus.FAIL if len(drivers) >= 2 else sv.CheckStatus.PASS,
            f"net has {len(drivers)} unconditional driver(s)",
            net,
        )

    # E5: open-drain bias. Differential-negative lines bias toward ground;
    # ordinary and differential-positive lines bias toward a positive rail.
    for net in analysis.nets.values():
        open_drains = [
            pin
            for pin in analysis.active_connections(net)
            if cmp.DriveStyle.OPEN_DRAIN in pin.erc.drive_styles
        ]
        if not open_drains:
            continue
        negative = all(
            isinstance(pin.spec, cmp.DigitalPinSpec)
            and pin.spec.interface is not None
            and pin.spec.interface.polarity is cmp.DifferentialPolarity.NEGATIVE
            for pin in open_drains
        )
        polarity = "non_positive" if negative else "positive"
        has_bias, voltage = _resistive_bias(analysis, net, polarity=polarity)
        direction = (
            "pull-down to a non-positive rail"
            if negative
            else "pull-up to a positive rail"
        )
        add(
            "E5",
            sv.CheckStatus.PASS if has_bias else sv.CheckStatus.FAIL,
            (
                f"open-drain net has a resistor {direction}"
                if has_bias
                else f"open-drain net has no resistor {direction}"
            ),
            net,
            (voltage,),
        )
    return checks


def check_design(design: "Design") -> ElectricalReport:
    analysis = DesignAnalysis(design)
    checks = _check_global_nets(analysis, design.short_name)

    def visit(current, path):
        checks.extend(_check_local(current, path, analysis))
        for module in current.modules:
            visit(module, f"{path}/{module.short_name}")

    visit(design, design.short_name)
    return ElectricalReport(tuple(checks))


def electrical_coverage(design: "Design"):
    typed = 0
    total = 0
    rails = 0
    ratings = 0

    def visit(current):
        nonlocal typed, total, rails, ratings
        rails += len(current._declared_rails)
        for component in current.components.values():
            if component.virtual or component.dnp:
                continue
            component_pins = list(component.pins)
            total += len(component_pins)
            typed += sum(
                not isinstance(pin.spec, cmp.UnspecifiedPinSpec)
                for pin in component_pins
            )
            ratings += len(component.abs_max) + len(component.recommended)
        for module in current.modules:
            visit(module)

    visit(design)
    return {
        "pins_typed": typed,
        "pins_total": total,
        "rails_declared": rails,
        "ratings_present": ratings,
    }
