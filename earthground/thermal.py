"""Declarative component power and thermal reporting."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable, Optional, Protocol

import earthground.components as cmp
import earthground.standard_values as sv
from earthground.analysis import DesignAnalysis, ResolvedComponent


@dataclass(frozen=True, kw_only=True)
class ThermalModel:
    r_ja: Optional[sv.ValueBounds] = None
    r_jb: Optional[sv.ValueBounds] = None
    r_jc_top: Optional[sv.ValueBounds] = None
    r_jc_bottom: Optional[sv.ValueBounds] = None
    psi_jt: Optional[sv.ValueBounds] = None
    psi_jb: Optional[sv.ValueBounds] = None

    def __post_init__(self):
        for name, value in vars(self).items():
            sv.require_bounds(value, "°C/W", name, allow_none=True)


@dataclass(frozen=True)
class PowerEstimate:
    status: sv.CheckStatus
    power: Optional[sv.ValueBounds]
    notes: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()


class PowerModel(Protocol):
    def estimate(
        self, component: cmp.Component, analysis: DesignAnalysis
    ) -> PowerEstimate: ...


@dataclass(frozen=True, kw_only=True)
class ConstantPower:
    power: sv.ValueBounds
    note: Optional[str] = None

    def __post_init__(self):
        sv.require_bounds(self.power, "W", "power")

    def estimate(self, component, analysis):
        status = (
            sv.CheckStatus.PASS
            if self.power.min is not None and self.power.max is not None
            else sv.CheckStatus.UNKNOWN
        )
        return PowerEstimate(
            status,
            self.power,
            () if self.note is None else (self.note,),
            self.power.source,
        )


@dataclass(frozen=True, kw_only=True)
class RailCurrent:
    pin: str
    current: sv.ValueBounds

    def __post_init__(self):
        sv.require_bounds(self.current, "A", "rail current")


@dataclass(frozen=True, kw_only=True)
class SupplyCurrentPower:
    rails: tuple[RailCurrent, ...]

    def estimate(self, component, analysis):
        total = None
        notes = []
        sources = []
        for rail in self.rails:
            try:
                pin = component.pins.by_name(rail.pin)
            except ValueError:
                return PowerEstimate(
                    sv.CheckStatus.UNKNOWN,
                    None,
                    (f"power-model pin {rail.pin} does not exist",),
                )
            net = analysis.net_for_pin(pin)
            if net is None or net.voltage is None or net.voltage_conflict:
                return PowerEstimate(
                    sv.CheckStatus.UNKNOWN,
                    None,
                    (f"voltage on {rail.pin} is unresolved",),
                    rail.current.source,
                )
            term = net.voltage * rail.current
            total = term if total is None else total + term
            notes.append(f"{rail.pin}: {net.name} voltage × declared supply current")
            sources.extend(net.voltage.source)
            sources.extend(rail.current.source)
        if total is None:
            return PowerEstimate(
                sv.CheckStatus.UNKNOWN, None, ("power model has no supply rails",)
            )
        status = (
            sv.CheckStatus.PASS
            if total.min is not None and total.max is not None
            else sv.CheckStatus.UNKNOWN
        )
        return PowerEstimate(
            status,
            total,
            tuple(notes),
            tuple(dict.fromkeys(sources)),
        )


@dataclass(frozen=True, kw_only=True)
class CallablePower:
    function: Callable[[cmp.Component, DesignAnalysis], PowerEstimate]

    def estimate(self, component, analysis):
        result = self.function(component, analysis)
        if not isinstance(result, PowerEstimate):
            raise TypeError("Custom power callable must return PowerEstimate")
        return result


@dataclass(frozen=True)
class ThermalRow:
    reference_designator: str
    manufacturer_part_number: str
    thermal_metric: Optional[str]
    thermal_resistance: Optional[sv.ValueBounds]
    footprint: Optional[str]
    x: Optional[float]
    y: Optional[float]
    rotation: Optional[float]
    layer: Optional[str]
    power_dissipation: Optional[sv.ValueBounds]
    junction_temperature: Optional[sv.ValueBounds]
    status: sv.CheckStatus
    notes: tuple[str, ...]
    sources: tuple[str, ...]


@dataclass(frozen=True)
class ThermalReport:
    rows: tuple[ThermalRow, ...]

    def write_csv(self, path: str | Path) -> Path:
        destination = Path(path)
        with destination.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                (
                    "reference designator",
                    "manufacturer part number",
                    "R_θJC",
                    "footprint",
                    "x",
                    "y",
                    "rotation",
                    "layer",
                    "power dissipation",
                    "notes",
                )
            )
            for row in self.rows:
                notes = list(row.notes)
                if row.thermal_metric:
                    notes.append(f"thermal metric: {row.thermal_metric}")
                if row.junction_temperature is not None:
                    notes.append(f"estimated junction: {row.junction_temperature}")
                if row.sources:
                    notes.append(f"sources: {', '.join(row.sources)}")
                writer.writerow(
                    (
                        row.reference_designator,
                        row.manufacturer_part_number,
                        (
                            ""
                            if row.thermal_resistance is None
                            else row.thermal_resistance
                        ),
                        row.footprint or "",
                        "" if row.x is None else row.x,
                        "" if row.y is None else row.y,
                        "" if row.rotation is None else row.rotation,
                        row.layer or "",
                        "" if row.power_dissipation is None else row.power_dissipation,
                        "; ".join(notes),
                    )
                )
        return destination


def _exact_bounds(value: Decimal, units: str):
    return sv.ValueBounds(units, value, typ=value, max=value)


def _resistor_power(component: cmp.Resistor, analysis: DesignAnalysis):
    pins = tuple(component.pins)
    if len(pins) != 2:
        return PowerEstimate(sv.CheckStatus.UNKNOWN, None, ("resistor is not two-pin",))
    nets = [analysis.net_for_pin(pin) for pin in pins]
    if any(net is None or net.voltage is None or net.voltage_conflict for net in nets):
        return PowerEstimate(
            sv.CheckStatus.UNKNOWN,
            None,
            ("one or both resistor terminal voltages are unresolved",),
        )
    left, right = (net.voltage for net in nets)
    if None in (left.min, left.max, right.min, right.max):
        return PowerEstimate(
            sv.CheckStatus.UNKNOWN,
            None,
            ("resistor terminal voltage bounds are incomplete",),
            tuple(dict.fromkeys(left.source + right.source)),
        )
    differences = (
        left.min - right.min,
        left.min - right.max,
        left.max - right.min,
        left.max - right.max,
    )
    maximum = max(abs(value) for value in differences)
    intervals_overlap = not (left.max < right.min or right.max < left.min)
    minimum = (
        Decimal(0) if intervals_overlap else min(abs(value) for value in differences)
    )
    typical = None
    if left.typ is not None and right.typ is not None:
        typical = abs(left.typ - right.typ)
    resistance = component.value.value
    power = sv.watts(
        minimum * minimum / resistance,
        typ=None if typical is None else typical * typical / resistance,
        max=maximum * maximum / resistance,
        source=tuple(dict.fromkeys(left.source + right.source)),
    )
    return PowerEstimate(
        sv.CheckStatus.PASS,
        power,
        ("resistance treated as exact nominal value",),
        power.source,
    )


def estimate_power(component: cmp.Component, analysis: DesignAnalysis):
    if component.power is not None:
        return component.power.estimate(component, analysis)
    if isinstance(component, cmp.Capacitor):
        zero = sv.watts(0, typ=0, max=0)
        return PowerEstimate(
            sv.CheckStatus.PASS,
            zero,
            ("capacitor steady-state dissipation modeled as zero",),
        )
    if isinstance(component, cmp.Resistor):
        return _resistor_power(component, analysis)
    return PowerEstimate(
        sv.CheckStatus.UNKNOWN,
        None,
        ("component has no power model",),
    )


def _selected_resistance(model: Optional[ThermalModel]):
    if model is None:
        return None, None
    for name, value in (
        ("RθJB", model.r_jb),
        ("RθJC(bottom)", model.r_jc_bottom),
        ("RθJC(top)", model.r_jc_top),
        ("RθJA", model.r_ja),
    ):
        if value is not None:
            return name, value
    return None, None


def _row(design, resolved: ResolvedComponent, analysis: DesignAnalysis):
    component = resolved.component
    power = estimate_power(component, analysis)
    metric, resistance = _selected_resistance(component.thermal)
    notes = list(power.notes)
    sources = list(power.sources)
    junction = None
    status = power.status
    if component.thermal is None or resistance is None:
        status = sv.CheckStatus.UNKNOWN
        notes.append("component has no usable thermal resistance")
    elif component.thermal.r_ja is not None:
        if design._ambient is None or power.power is None:
            status = sv.CheckStatus.UNKNOWN
            notes.append("junction estimate requires ambient and power")
        else:
            junction = design._ambient + component.thermal.r_ja * power.power
            sources.extend(design._ambient.source)
            sources.extend(component.thermal.r_ja.source)
            if "tj" in component.abs_max:
                coverage = component.abs_max["tj"].covers(junction)
                if coverage is not sv.CheckStatus.PASS:
                    status = coverage
                    notes.append(
                        "junction estimate is not conclusively within Tj limit"
                    )
            else:
                status = sv.CheckStatus.UNKNOWN
                notes.append("component has no absolute-maximum Tj rating")
    else:
        status = sv.CheckStatus.UNKNOWN
        notes.append(
            f"{metric} is reportable but cannot estimate junction from ambient"
        )
    placement = resolved.placement
    if placement is None:
        status = sv.CheckStatus.UNKNOWN
        notes.append("component has no explicit placement")
    footprint = getattr(component.footprint, "name", None)
    return ThermalRow(
        resolved.refdes,
        component.mpn or component.name,
        metric,
        resistance,
        footprint,
        None if placement is None else placement.component.x,
        None if placement is None else placement.component.y,
        None if placement is None else placement.component.angle,
        None if placement is None else placement.layer.name,
        power.power,
        junction,
        status,
        tuple(notes),
        tuple(
            dict.fromkeys(
                sources + ([] if resistance is None else list(resistance.source))
            )
        ),
    )


def build_report(design) -> ThermalReport:
    analysis = DesignAnalysis(design)
    rows = tuple(
        _row(design, resolved, analysis)
        for resolved in analysis.components
        if not resolved.component.dnp
    )
    return ThermalReport(rows)
