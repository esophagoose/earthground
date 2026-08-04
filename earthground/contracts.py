"""Declarative required-external component contracts."""

from __future__ import annotations

import math
import enum
from dataclasses import dataclass
from typing import Optional

import earthground.components as cmp
import earthground.standard_values as sv
from earthground.analysis import DesignAnalysis


@dataclass(frozen=True, kw_only=True)
class Requirement:
    id: str
    source: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("Requirement requires a stable id")


@dataclass(frozen=True, kw_only=True)
class Decoupling(Requirement):
    pin: str
    capacitance: sv.ValueBounds
    return_to: str = "GND"
    count: int = 1
    per_pin: bool = False
    max_distance_mm: Optional[float] = None

    def __post_init__(self):
        super().__post_init__()
        sv.require_bounds(self.capacitance, "F", "capacitance")
        if self.count < 1:
            raise ValueError("Decoupling count must be positive")
        if self.max_distance_mm is not None and self.max_distance_mm <= 0:
            raise ValueError("max_distance_mm must be positive")


@dataclass(frozen=True, kw_only=True)
class Bypass(Decoupling):
    pass


@dataclass(frozen=True, kw_only=True)
class PullResistor(Requirement):
    pin: str
    to: str
    resistance: sv.ValueBounds

    def __post_init__(self):
        super().__post_init__()
        sv.require_bounds(self.resistance, "Ω", "resistance")


@dataclass(frozen=True, kw_only=True)
class SameNet(Requirement):
    pins: tuple[str, ...]

    def __post_init__(self):
        super().__post_init__()
        if len(self.pins) < 2:
            raise ValueError("SameNet requires at least two pins")


@dataclass(frozen=True, kw_only=True)
class TieIfUnused(Requirement):
    pins: tuple[str, ...]
    to: str


@dataclass(frozen=True, kw_only=True)
class LeaveOpenIfUnused(Requirement):
    pins: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class RoutingConstraint(Requirement):
    pins: tuple[str, ...]
    min_trace_width_mm: Optional[float] = None
    z_diff: Optional[sv.ValueBounds] = None
    note: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        if self.min_trace_width_mm is not None and self.min_trace_width_mm <= 0:
            raise ValueError("min_trace_width_mm must be positive")
        sv.require_bounds(self.z_diff, "Ω", "z_diff", allow_none=True)


class CheckKind(enum.Enum):
    VERIFICATION = "Verification"
    ADVISORY = "Advisory"


@dataclass(frozen=True)
class ContractCheck:
    check_id: str
    requirement_id: str
    status: sv.CheckStatus
    refdes: str
    message: str
    source: Optional[str] = None
    waiver_reason: Optional[str] = None
    kind: CheckKind = CheckKind.VERIFICATION

    @property
    def is_accepted(self):
        return (
            self.status is sv.CheckStatus.PASS
            or self.waiver_reason is not None
            or self.kind is CheckKind.ADVISORY
        )

    def __str__(self):
        waiver = f" [waived: {self.waiver_reason}]" if self.waiver_reason else ""
        source = f" [source: {self.source}]" if self.source else ""
        return (
            f"{self.check_id} {self.status.value} at {self.refdes}: "
            f"{self.message}{source}{waiver}"
        )


@dataclass(frozen=True)
class ContractReport:
    checks: tuple[ContractCheck, ...]

    @property
    def items(self):
        return self.checks

    @property
    def passes(self):
        return tuple(
            check for check in self.checks if check.status is sv.CheckStatus.PASS
        )

    @property
    def blocking(self):
        return tuple(check for check in self.checks if not check.is_accepted)

    @property
    def failures(self):
        return self.blocking

    @property
    def unknowns(self):
        return tuple(
            check
            for check in self.checks
            if check.status is sv.CheckStatus.UNKNOWN
            and check.waiver_reason is None
            and check.kind is CheckKind.VERIFICATION
        )

    @property
    def is_valid(self):
        return not self.failures


def _pin(component, name):
    try:
        return component.pins.by_name(name)
    except ValueError:
        return None


def _named_net(analysis, component, name):
    pin = _pin(component, name)
    if pin is not None:
        net = analysis.net_for_pin(pin)
        if net is not None:
            return net
    return analysis.nets.get(name)


def _required_minimum(bounds):
    if bounds.min is not None:
        return bounds.min
    if bounds.typ is not None:
        return bounds.typ
    return bounds.max


def _capacitors_between(analysis, target, return_net):
    matches = []
    for connection in analysis.active_connections(target):
        capacitor = connection.parent
        if not isinstance(capacitor, cmp.Capacitor) or capacitor.dnp:
            continue
        other = next((pin for pin in capacitor.pins if pin is not connection), None)
        if other is not None and analysis.net_for_pin(other) is return_net:
            matches.append(capacitor)
    return tuple(dict.fromkeys(matches))


def _pad_position(resolved, pin):
    footprint = resolved.component.footprint
    placement = resolved.placement
    if footprint is None or placement is None:
        return None
    pad = footprint.pads.get(pin.index)
    if pad is None:
        pad = footprint.pads.get(str(pin.index))
    if pad is None:
        return None
    x, y = pad.location
    if placement.layer.name == "BOTTOM":
        x = -x
    angle = math.radians(placement.component.angle)
    return (
        placement.component.x + x * math.cos(angle) - y * math.sin(angle),
        placement.component.y + x * math.sin(angle) + y * math.cos(angle),
    )


def _decoupling_pad_distance(analysis, resolved, capacitor, target, required_pin_name):
    support = analysis.component_for(capacitor)
    if support is None:
        return None
    device_pads = [
        position
        for pin in resolved.component.pins.all_with_name(required_pin_name)
        if analysis.net_for_pin(pin) is target
        if (position := _pad_position(resolved, pin)) is not None
    ]
    capacitor_pads = [
        position
        for pin in capacitor.pins
        if analysis.net_for_pin(pin) is target
        if (position := _pad_position(support, pin)) is not None
    ]
    if not device_pads or not capacitor_pads:
        return None
    return min(
        math.hypot(left[0] - right[0], left[1] - right[1])
        for left in device_pads
        for right in capacitor_pads
    )


def _check_decoupling(analysis, resolved, requirement):
    component = resolved.component
    pins = component.pins.all_with_name(requirement.pin)
    target_nets = {
        analysis.net_for_pin(pin)
        for pin in pins
        if analysis.net_for_pin(pin) is not None
    }
    return_net = _named_net(analysis, component, requirement.return_to)
    if not pins:
        return [
            ("topology", sv.CheckStatus.FAIL, f"pin {requirement.pin} does not exist")
        ]
    if len(target_nets) != 1 or return_net is None:
        return [
            ("topology", sv.CheckStatus.UNKNOWN, "target or return net is unresolved")
        ]
    target = next(iter(target_nets))
    capacitors = _capacitors_between(analysis, target, return_net)
    if not capacitors:
        return [
            (
                "topology",
                sv.CheckStatus.FAIL,
                f"no capacitor connects {target.name} to {return_net.name}",
            )
        ]
    required_count = max(requirement.count, len(pins) if requirement.per_pin else 1)
    local_capacitors = tuple(
        capacitor
        for capacitor in capacitors
        if capacitor.parent is resolved.component.parent
    )
    candidates = (
        local_capacitors if len(local_capacitors) >= required_count else capacitors
    )
    checks = [
        ("topology", sv.CheckStatus.PASS, f"found {len(candidates)} capacitor(s)")
    ]
    checks.append(
        (
            "count",
            (
                sv.CheckStatus.PASS
                if len(candidates) >= required_count
                else sv.CheckStatus.FAIL
            ),
            f"found {len(candidates)} capacitor(s); requires {required_count}",
        )
    )
    minimum = _required_minimum(requirement.capacitance)
    if minimum is None:
        checks.append(
            (
                "capacitance",
                sv.CheckStatus.UNKNOWN,
                "required capacitance is incomplete",
            )
        )
    else:
        installed = sum(
            (capacitor.value.value for capacitor in candidates), start=minimum * 0
        )
        checks.append(
            (
                "capacitance",
                sv.CheckStatus.PASS if installed >= minimum else sv.CheckStatus.FAIL,
                f"installed nominal capacitance is {installed}F; requires at least {minimum}F",
            )
        )
    if requirement.max_distance_mm is not None:
        if resolved.placement is None:
            checks.append(
                (
                    "distance",
                    sv.CheckStatus.UNKNOWN,
                    "explicit placement is unavailable for the required component",
                )
            )
        else:
            distances = [
                _decoupling_pad_distance(
                    analysis,
                    resolved,
                    capacitor,
                    target,
                    requirement.pin,
                )
                for capacitor in candidates
            ]
            distances = [distance for distance in distances if distance is not None]
            enough_close = sum(
                distance <= requirement.max_distance_mm for distance in distances
            )
            unknown_count = len(candidates) - len(distances)
            if enough_close >= required_count:
                status = sv.CheckStatus.PASS
            elif unknown_count:
                status = sv.CheckStatus.UNKNOWN
            else:
                status = sv.CheckStatus.FAIL
            checks.append(
                (
                    "distance",
                    status,
                    (
                        f"{enough_close} capacitor(s) have supply-pad centres within "
                        f"{requirement.max_distance_mm} mm; "
                        f"measured distances: "
                        f"{', '.join(f'{distance:.3f} mm' for distance in distances) or 'none'}; "
                        f"{unknown_count} candidate placement(s) are unavailable"
                    ),
                )
            )
    return checks


def _check_pull(analysis, resolved, requirement):
    component = resolved.component
    pin = _pin(component, requirement.pin)
    target = None if pin is None else analysis.net_for_pin(pin)
    destination = _named_net(analysis, component, requirement.to)
    if pin is None:
        return [
            ("topology", sv.CheckStatus.FAIL, f"pin {requirement.pin} does not exist")
        ]
    if target is None or destination is None:
        return [
            (
                "topology",
                sv.CheckStatus.UNKNOWN,
                "target or destination net is unresolved",
            )
        ]
    matches = [
        resistor
        for resistor, other in analysis.resistor_branches(target)
        if other is destination
    ]
    if not matches:
        return [
            (
                "topology",
                sv.CheckStatus.FAIL,
                f"no resistor pulls {requirement.pin} to {requirement.to}",
            )
        ]
    if len(matches) > 1:
        return [
            (
                "topology",
                sv.CheckStatus.UNKNOWN,
                "multiple matching pull resistors found",
            )
        ]
    resistor = matches[0]
    status = requirement.resistance.covers(resistor.value)
    return [
        ("topology", sv.CheckStatus.PASS, f"found {resistor.refdes}"),
        ("resistance", status, f"pull resistance is {resistor.value}"),
    ]


def _check_same_net(analysis, resolved, requirement):
    nets = []
    for name in requirement.pins:
        pin = _pin(resolved.component, name)
        if pin is None:
            return [("topology", sv.CheckStatus.FAIL, f"pin {name} does not exist")]
        nets.append(analysis.net_for_pin(pin))
    if any(net is None for net in nets):
        return [
            (
                "topology",
                sv.CheckStatus.FAIL,
                "one or more required pins are unconnected",
            )
        ]
    passed = all(net is nets[0] for net in nets[1:])
    return [
        (
            "topology",
            sv.CheckStatus.PASS if passed else sv.CheckStatus.FAIL,
            "pins share one net" if passed else "pins do not share one net",
        )
    ]


def _used_by_other_component(analysis, component, net):
    return any(pin.parent is not component for pin in analysis.active_connections(net))


def _check_unused_policy(analysis, resolved, requirement):
    results = []
    for name in requirement.pins:
        pin = _pin(resolved.component, name)
        if pin is None:
            results.append((name, sv.CheckStatus.FAIL, f"pin {name} does not exist"))
            continue
        net = analysis.net_for_pin(pin)
        used = net is not None and _used_by_other_component(
            analysis, resolved.component, net
        )
        if isinstance(requirement, TieIfUnused):
            destination = _named_net(analysis, resolved.component, requirement.to)
            if not used and destination is None:
                results.append(
                    (
                        name,
                        sv.CheckStatus.UNKNOWN,
                        f"destination {requirement.to} is unresolved",
                    )
                )
                continue
            passed = used or (net is not None and net is destination)
            results.append(
                (
                    name,
                    sv.CheckStatus.PASS if passed else sv.CheckStatus.FAIL,
                    (
                        "pin is used"
                        if used
                        else f"unused pin must be tied to {requirement.to}"
                    ),
                )
            )
        else:
            open_pin = net is None or not analysis.active_connections(net)
            # The pin itself is an active connection, so a one-pin net is open electrically.
            open_pin = net is None or set(analysis.active_connections(net)) == {pin}
            passed = used or open_pin
            results.append(
                (
                    name,
                    sv.CheckStatus.PASS if passed else sv.CheckStatus.FAIL,
                    "pin is used" if used else "unused pin must be left open",
                )
            )
    return results


def _evaluate(analysis, resolved, requirement):
    if isinstance(requirement, Decoupling):
        return _check_decoupling(analysis, resolved, requirement)
    if isinstance(requirement, PullResistor):
        return _check_pull(analysis, resolved, requirement)
    if isinstance(requirement, SameNet):
        return _check_same_net(analysis, resolved, requirement)
    if isinstance(requirement, (TieIfUnused, LeaveOpenIfUnused)):
        return _check_unused_policy(analysis, resolved, requirement)
    if isinstance(requirement, RoutingConstraint):
        missing = [
            name for name in requirement.pins if _pin(resolved.component, name) is None
        ]
        if missing:
            return [
                (
                    "routing",
                    sv.CheckStatus.FAIL,
                    f"routing constraint references missing pins: {', '.join(missing)}",
                )
            ]
        nets = []
        for name in requirement.pins:
            net = analysis.net_for_pin(_pin(resolved.component, name))
            if net is not None and net.name not in nets:
                nets.append(net.name)
        if not nets:
            return [
                (
                    "routing",
                    sv.CheckStatus.UNKNOWN,
                    "routing nets are unresolved",
                )
            ]
        typed_results = []
        if requirement.min_trace_width_mm is not None:
            minimum_m = requirement.min_trace_width_mm / 1000
            classes = [
                item
                for page in analysis.design.iter_designs()
                for item in page._net_classes.values()
                if set(nets).issubset(item.nets)
            ]
            widths = [
                item.track_width.typ
                for item in classes
                if item.track_width is not None and item.track_width.typ is not None
            ]
            if widths:
                passed = any(float(width) >= minimum_m for width in widths)
                typed_results.append(
                    (
                        "routing",
                        sv.CheckStatus.PASS if passed else sv.CheckStatus.FAIL,
                        f"declared net-class width {'meets' if passed else 'does not meet'} "
                        f"{requirement.min_trace_width_mm} mm minimum",
                    )
                )
            else:
                typed_results.append(
                    (
                        "routing",
                        sv.CheckStatus.UNKNOWN,
                        "no matching typed net-class width is declared",
                    )
                )
        if requirement.z_diff is not None:
            pairs = [
                pair
                for page in analysis.design.iter_designs()
                for pair in page._diff_pairs
                if set(pair.nets) == set(nets)
            ]
            if not pairs or pairs[0].z_diff is None:
                typed_results.append(
                    (
                        "routing-impedance",
                        sv.CheckStatus.UNKNOWN,
                        "no matching typed differential-pair impedance is declared",
                    )
                )
            else:
                status = requirement.z_diff.covers(pairs[0].z_diff)
                typed_results.append(
                    (
                        "routing-impedance",
                        status,
                        (
                            "declared differential-pair impedance is compatible"
                            if status is sv.CheckStatus.PASS
                            else "declared differential-pair impedance is incompatible"
                        ),
                    )
                )
        if typed_results:
            return typed_results
        detail = requirement.note or "routing constraint requires PCB trace evidence"
        return [
            (
                "routing",
                sv.CheckStatus.UNKNOWN,
                detail,
                CheckKind.ADVISORY,
            )
        ]
    return [
        (
            "declaration",
            sv.CheckStatus.FAIL,
            f"unsupported requirement {type(requirement).__name__}",
        )
    ]


def check_design(design) -> ContractReport:
    analysis = DesignAnalysis(design)
    waivers = {}
    for page in design.iter_designs():
        waivers.update(page._contract_waivers)
    checks = []
    for resolved in analysis.components:
        component = resolved.component
        if component.dnp:
            continue
        ids = [requirement.id for requirement in component.requires]
        if len(ids) != len(set(ids)):
            checks.append(
                ContractCheck(
                    "contracts.declaration",
                    "contracts",
                    sv.CheckStatus.FAIL,
                    resolved.refdes,
                    "component requirement ids are not unique",
                )
            )
            continue
        for requirement in component.requires:
            for result in _evaluate(analysis, resolved, requirement):
                aspect, status, message, *metadata = result
                check_id = f"{requirement.id}.{aspect}"
                checks.append(
                    ContractCheck(
                        check_id,
                        requirement.id,
                        status,
                        resolved.refdes,
                        message,
                        requirement.source,
                        waivers.get((component, check_id)),
                        metadata[0] if metadata else CheckKind.VERIFICATION,
                    )
                )
    return ContractReport(tuple(checks))
