"""Three-level and resistor-biased configuration strap analysis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import earthground.components as cmp
import earthground.standard_values as sv
from earthground.analysis import DesignAnalysis


@dataclass(frozen=True, kw_only=True)
class StrapLevel:
    name: str
    ratio: sv.ValueBounds
    meaning: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("Strap level requires a name")
        sv.require_bounds(self.ratio, "", "Strap level ratio")


@dataclass(frozen=True, kw_only=True)
class StrapPin:
    id: str
    pin: str
    reference: str
    levels: tuple[StrapLevel, ...]
    internal_pull_up: Optional[sv.ValueBounds] = None
    internal_pull_down: Optional[sv.ValueBounds] = None
    sampled_on: Optional[str] = None
    source: Optional[str] = None

    def __post_init__(self):
        if not self.id or not self.pin or not self.reference:
            raise ValueError("Strap id, pin, and reference are required")
        if not self.levels:
            raise ValueError("Strap requires at least one level")
        sv.require_bounds(
            self.internal_pull_up, "Ω", "internal_pull_up", allow_none=True
        )
        sv.require_bounds(
            self.internal_pull_down, "Ω", "internal_pull_down", allow_none=True
        )
        names = [level.name for level in self.levels]
        if len(names) != len(set(names)):
            raise ValueError("Strap level names must be unique")


@dataclass(frozen=True)
class StrapExpectation:
    level: str
    reason: str


@dataclass(frozen=True)
class StrapResult:
    refdes: str
    strap_id: str
    pin: str
    status: sv.CheckStatus
    ratio: Optional[sv.ValueBounds]
    level: Optional[str]
    meaning: Optional[str]
    default_level: Optional[str]
    expected_level: Optional[str]
    determining_components: tuple[str, ...]
    message: str
    sources: tuple[str, ...] = ()

    @property
    def externally_overridden(self):
        return (
            self.level is not None
            and self.default_level is not None
            and self.level != self.default_level
        )


@dataclass(frozen=True)
class StrapReport:
    results: tuple[StrapResult, ...]

    @property
    def failures(self):
        return tuple(
            result for result in self.results if result.status is sv.CheckStatus.FAIL
        )

    @property
    def unknowns(self):
        return tuple(
            result for result in self.results if result.status is sv.CheckStatus.UNKNOWN
        )

    @property
    def is_valid(self):
        return not self.failures and not self.unknowns


def _complete_resistance(bounds: sv.ValueBounds) -> Optional[tuple[Decimal, Decimal]]:
    if bounds.min is None or bounds.max is None or bounds.min <= 0:
        return None
    return bounds.min, bounds.max


def _resistor_bounds(resistor: cmp.Resistor) -> tuple[Decimal, Decimal]:
    value = resistor.value.value
    return value, value


def _parallel_conductance(
    resistances: list[tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal]:
    return (
        sum((Decimal(1) / upper for _, upper in resistances), Decimal(0)),
        sum((Decimal(1) / lower for lower, _ in resistances), Decimal(0)),
    )


def _divider_ratio(
    pull_up: list[tuple[Decimal, Decimal]],
    pull_down: list[tuple[Decimal, Decimal]],
    sources,
) -> Optional[sv.ValueBounds]:
    if not pull_up and not pull_down:
        return None
    if not pull_up:
        return sv.ratio(0, typ=0, max=0, source=sources)
    if not pull_down:
        return sv.ratio(1, typ=1, max=1, source=sources)
    up_min, up_max = _parallel_conductance(pull_up)
    down_min, down_max = _parallel_conductance(pull_down)
    lower = up_min / (up_min + down_max)
    upper = up_max / (up_max + down_min)
    typical = lower if lower == upper else (lower + upper) / Decimal(2)
    typical = min(max(typical, lower), upper)
    return sv.ratio(lower, typ=typical, max=upper, source=sources)


def _resolve_level(strap: StrapPin, ratio: Optional[sv.ValueBounds]):
    if ratio is None:
        return None, None
    matches = [
        level
        for level in strap.levels
        if level.ratio.covers(ratio) is sv.CheckStatus.PASS
    ]
    if len(matches) != 1:
        return None, None
    return matches[0].name, matches[0].meaning


def _internal_ratio(strap: StrapPin):
    up = []
    down = []
    if strap.internal_pull_up is not None:
        value = _complete_resistance(strap.internal_pull_up)
        if value is None:
            return None
        up.append(value)
    if strap.internal_pull_down is not None:
        value = _complete_resistance(strap.internal_pull_down)
        if value is None:
            return None
        down.append(value)
    return _divider_ratio(up, down, (strap.source,) if strap.source else ())


def _resolve_strap(analysis, resolved_component, strap, expectation):
    component = resolved_component.component
    try:
        pin = component.pins.by_name(strap.pin)
        reference_pin = component.pins.by_name(strap.reference)
    except ValueError as exc:
        return StrapResult(
            resolved_component.refdes,
            strap.id,
            strap.pin,
            sv.CheckStatus.FAIL,
            None,
            None,
            None,
            None,
            None if expectation is None else expectation.level,
            (),
            f"invalid strap declaration: {exc}",
        )
    net = analysis.net_for_pin(pin)
    reference_net = analysis.net_for_pin(reference_pin)
    default_ratio = _internal_ratio(strap)
    default_level, _ = _resolve_level(strap, default_ratio)
    expected_level = None if expectation is None else expectation.level
    sources = tuple(source for source in (strap.source,) if source)
    if net is None or reference_net is None:
        return StrapResult(
            resolved_component.refdes,
            strap.id,
            strap.pin,
            sv.CheckStatus.UNKNOWN,
            None,
            None,
            None,
            default_level,
            expected_level,
            (),
            "strap net or reference rail is unresolved",
            sources,
        )
    if net.name == reference_net.name:
        ratio = sv.ratio(1, typ=1, max=1, source=sources)
        determining = (reference_net.name,)
    elif net.name == analysis.design.ground:
        ratio = sv.ratio(0, typ=0, max=0, source=sources)
        determining = (analysis.design.ground,)
    else:
        up = []
        down = []
        determining_items = []
        if strap.internal_pull_up is not None:
            value = _complete_resistance(strap.internal_pull_up)
            if value is None:
                return _unknown_result(
                    resolved_component,
                    strap,
                    default_level,
                    expected_level,
                    "internal pull-up bounds are incomplete",
                    sources,
                )
            up.append(value)
        if strap.internal_pull_down is not None:
            value = _complete_resistance(strap.internal_pull_down)
            if value is None:
                return _unknown_result(
                    resolved_component,
                    strap,
                    default_level,
                    expected_level,
                    "internal pull-down bounds are incomplete",
                    sources,
                )
            down.append(value)

        branches = list(analysis.resistor_branches(net))
        if len(branches) > 2:
            return _unknown_result(
                resolved_component,
                strap,
                default_level,
                expected_level,
                "more than two external resistor branches require nodal analysis",
                sources,
                tuple(_refdes(analysis, resistor) for resistor, _ in branches),
            )
        branch_resistors = {resistor for resistor, _ in branches}
        unsupported = []
        for connection in analysis.active_connections(net):
            parent = connection.parent
            if parent is component or parent in branch_resistors:
                continue
            characteristics = connection.erc
            if len(parent.pins) == 1 and not (
                characteristics.directions
                & {cmp.PinDirection.OUTPUT, cmp.PinDirection.BIDIRECTIONAL}
            ):
                continue
            if characteristics.directions & {
                cmp.PinDirection.OUTPUT,
                cmp.PinDirection.BIDIRECTIONAL,
            } or isinstance(parent, cmp.PASSIVE_TYPES):
                unsupported.append(parent)
        if unsupported:
            return _unknown_result(
                resolved_component,
                strap,
                default_level,
                expected_level,
                "strap net contains an unsupported active or passive branch",
                sources,
                tuple(_refdes(analysis, item) for item in unsupported),
            )
        for resistor, other_net in branches:
            determining_items.append(_refdes(analysis, resistor))
            if other_net is None:
                return _unknown_result(
                    resolved_component,
                    strap,
                    default_level,
                    expected_level,
                    "external resistor endpoint is unresolved",
                    sources,
                    tuple(determining_items),
                )
            if other_net.name == reference_net.name:
                up.append(_resistor_bounds(resistor))
            elif other_net.name == analysis.design.ground:
                down.append(_resistor_bounds(resistor))
            else:
                return _unknown_result(
                    resolved_component,
                    strap,
                    default_level,
                    expected_level,
                    f"external resistor terminates at unsupported net {other_net.name}",
                    sources,
                    tuple(determining_items),
                )
        ratio = _divider_ratio(up, down, sources)
        determining = tuple(determining_items)

    level, meaning = _resolve_level(strap, ratio)
    if level is None:
        status = sv.CheckStatus.UNKNOWN
        message = "computed ratio does not fit entirely within one strap level"
    elif expected_level is not None and level != expected_level:
        status = sv.CheckStatus.FAIL
        message = f"resolved {level}, expected {expected_level}: {expectation.reason}"
    else:
        status = sv.CheckStatus.PASS
        message = f"resolved {level}: {meaning}"
        if default_level is not None and level != default_level:
            message += f"; external bias overrides internal default {default_level}"
    return StrapResult(
        resolved_component.refdes,
        strap.id,
        strap.pin,
        status,
        ratio,
        level,
        meaning,
        default_level,
        expected_level,
        determining,
        message,
        sources,
    )


def _unknown_result(
    resolved_component,
    strap,
    default_level,
    expected_level,
    message,
    sources=(),
    determining=(),
):
    return StrapResult(
        resolved_component.refdes,
        strap.id,
        strap.pin,
        sv.CheckStatus.UNKNOWN,
        None,
        None,
        None,
        default_level,
        expected_level,
        determining,
        message,
        sources,
    )


def _refdes(analysis, component):
    resolved = analysis.component_for(component)
    return component.refdes if resolved is None else resolved.refdes


def check_design(design) -> StrapReport:
    analysis = DesignAnalysis(design)
    expectations = {}
    for page in design.iter_designs():
        expectations.update(page._strap_expectations)
    results = []
    for resolved_component in analysis.components:
        component = resolved_component.component
        if component.dnp:
            continue
        for strap in component.strap_pins:
            expectation = expectations.get((component, strap.id))
            results.append(
                _resolve_strap(analysis, resolved_component, strap, expectation)
            )
    return StrapReport(tuple(results))
