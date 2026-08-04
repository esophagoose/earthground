"""Strict helpers for declaring typed electrical intent in library parts.

Library components should never silently fall back to ``UnspecifiedPinSpec``.
This module keeps large package pin maps readable while requiring every logical
pin name to be classified explicitly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import earthground.components as cmp
import earthground.standard_values as sv


def typed_pin_map(
    pinout: Mapping[object, str],
    *,
    digital_inputs: Iterable[str] = (),
    digital_outputs: Iterable[str] = (),
    digital_bidirectional: Iterable[str] = (),
    analog_inputs: Iterable[str] = (),
    analog_outputs: Iterable[str] = (),
    power_inputs: Mapping[str, sv.ValueBounds | None] | Iterable[str] = (),
    power_outputs: Mapping[str, sv.ValueBounds | None] | Iterable[str] = (),
    grounds: Iterable[str] = (),
    no_connects: Iterable[str] = (),
    passive: Iterable[str] = (),
    overrides: Mapping[str, cmp.BasePinSpec] | None = None,
    digital_voltage: sv.ValueBounds | None = None,
    digital_abs_max: sv.ValueBounds | None = None,
    source: str | None = None,
) -> dict[object, cmp.BasePinSpec]:
    """Return a physical-index-to-typed-spec map.

    Names may occur at more than one physical pin. Classifications are by
    logical name and therefore apply consistently to every occurrence.
    Unclassified and multiply classified names are rejected at construction
    time so a library migration cannot accidentally lose ERC evidence.
    """

    def names_and_voltages(value):
        if isinstance(value, Mapping):
            return set(value), value
        names = set(value)
        return names, {name: None for name in names}

    power_input_names, power_input_voltages = names_and_voltages(power_inputs)
    power_output_names, power_output_voltages = names_and_voltages(power_outputs)
    categories = {
        "digital input": set(digital_inputs),
        "digital output": set(digital_outputs),
        "digital bidirectional": set(digital_bidirectional),
        "analog input": set(analog_inputs),
        "analog output": set(analog_outputs),
        "power input": power_input_names,
        "power output": power_output_names,
        "ground": set(grounds),
        "no-connect": set(no_connects),
        "passive": set(passive),
        "override": set(overrides or {}),
    }
    declared = set(pinout.values())
    unknown = set().union(*categories.values()) - declared
    if unknown:
        raise ValueError(
            f"Typed pin classification names are absent: {sorted(unknown)}"
        )
    for name in declared:
        memberships = [label for label, names in categories.items() if name in names]
        if len(memberships) != 1:
            raise ValueError(
                f"Pin {name!r} must have exactly one typed classification; "
                f"found {memberships or 'none'}"
            )

    zero = sv.volts(0, typ=0, max=0, source=source)
    specs = {}
    for index, name in pinout.items():
        common = {"name": name, "source": source}
        if name in categories["digital input"]:
            spec = cmp.DigitalPinSpec.input(
                **common,
                voltage_operating=digital_voltage,
                voltage_abs_max=digital_abs_max,
            )
        elif name in categories["digital output"]:
            spec = cmp.DigitalPinSpec.output(
                **common,
                voltage_operating=digital_voltage,
                voltage_abs_max=digital_abs_max,
            )
        elif name in categories["digital bidirectional"]:
            spec = cmp.DigitalPinSpec.bidirectional(
                **common,
                voltage_operating=digital_voltage,
                voltage_abs_max=digital_abs_max,
            )
        elif name in categories["analog input"]:
            spec = cmp.AnalogPinSpec.input(
                **common,
                ratings=cmp.AnalogPinRatings(
                    voltage_operating=digital_voltage,
                    voltage_abs_max=digital_abs_max,
                ),
            )
        elif name in categories["analog output"]:
            spec = cmp.AnalogPinSpec.output(
                **common,
                ratings=cmp.AnalogPinRatings(
                    voltage_operating=digital_voltage,
                    voltage_abs_max=digital_abs_max,
                ),
            )
        elif name in power_input_names:
            spec = cmp.PowerPinSpec(
                **common,
                role=cmp.PowerRole.INPUT,
                voltage=power_input_voltages[name],
            )
        elif name in power_output_names:
            spec = cmp.PowerPinSpec(
                **common,
                role=cmp.PowerRole.OUTPUT,
                voltage=power_output_voltages[name],
            )
        elif name in categories["ground"]:
            spec = cmp.PowerPinSpec(
                **common,
                role=cmp.PowerRole.GROUND,
                voltage=zero,
                abs_max=zero,
            )
        elif name in categories["no-connect"]:
            spec = cmp.NoConnectPinSpec(**common)
        elif name in categories["passive"]:
            spec = cmp.PassivePinSpec(**common)
        else:
            spec = overrides[name]
        specs[index] = spec
    return specs


def passive_pin_map(pinout: Mapping[object, str], *, source: str | None = None):
    """Type every contact in a connector or fabricated feature as passive."""

    return typed_pin_map(pinout, passive=set(pinout.values()), source=source)
