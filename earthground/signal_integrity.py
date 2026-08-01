"""Declarative signal-integrity intent for PCB export and review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import earthground.standard_values as sv


def _safe_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    if "'" in value or '"' in value:
        raise ValueError(f"{label} cannot contain quote characters")


def _geometry(value, label):
    sv.require_bounds(value, "m", label, allow_none=True)
    if value is not None and value.typ is None:
        raise ValueError(f"{label} requires a typical value for KiCad routing")


@dataclass(frozen=True)
class NetClass:
    name: str
    nets: tuple[str, ...]
    clearance: Optional[sv.ValueBounds] = None
    track_width: Optional[sv.ValueBounds] = None
    diff_pair_width: Optional[sv.ValueBounds] = None
    diff_pair_gap: Optional[sv.ValueBounds] = None
    z_single: Optional[sv.ValueBounds] = None
    source: Optional[str] = None

    def __post_init__(self):
        _safe_identifier(self.name, "NetClass name")
        object.__setattr__(self, "nets", tuple(self.nets))
        if not self.nets:
            raise ValueError("NetClass requires at least one net")
        if len(self.nets) != len(set(self.nets)):
            raise ValueError("NetClass nets must be unique")
        for net in self.nets:
            _safe_identifier(net, "NetClass net")
        _geometry(self.clearance, "clearance")
        _geometry(self.track_width, "track_width")
        _geometry(self.diff_pair_width, "diff_pair_width")
        _geometry(self.diff_pair_gap, "diff_pair_gap")
        sv.require_bounds(self.z_single, "Ω", "z_single", allow_none=True)


@dataclass(frozen=True)
class DiffPair:
    nets: tuple[str, str]
    net_class: str
    z_diff: Optional[sv.ValueBounds] = None
    intra_pair_skew: Optional[sv.ValueBounds] = None
    max_vias: Optional[int] = None
    max_length: Optional[sv.ValueBounds] = None
    min_track_angle_deg: Optional[float] = None
    source: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "nets", tuple(self.nets))
        if len(self.nets) != 2 or self.nets[0] == self.nets[1]:
            raise ValueError("DiffPair requires two distinct nets")
        for net in self.nets:
            _safe_identifier(net, "DiffPair net")
        _safe_identifier(self.net_class, "DiffPair net_class")
        sv.require_bounds(self.z_diff, "Ω", "z_diff", allow_none=True)
        sv.require_bounds(self.intra_pair_skew, "m", "intra_pair_skew", allow_none=True)
        sv.require_bounds(self.max_length, "m", "max_length", allow_none=True)
        if self.intra_pair_skew is not None and self.intra_pair_skew.max is None:
            raise ValueError("intra_pair_skew requires a maximum")
        if self.max_length is not None and self.max_length.max is None:
            raise ValueError("max_length requires a maximum")
        if self.max_vias is not None and (
            not isinstance(self.max_vias, int) or self.max_vias < 0
        ):
            raise ValueError("max_vias must be a non-negative integer")
        if self.min_track_angle_deg is not None and not (
            0 < self.min_track_angle_deg <= 180
        ):
            raise ValueError("min_track_angle_deg must be in (0, 180]")


def validate_design(design) -> list[str]:
    from earthground.analysis import DesignAnalysis

    errors = []
    available_nets = set(DesignAnalysis(design).nets)
    classes = design._net_classes
    for net_class in classes.values():
        missing = sorted(set(net_class.nets) - available_nets)
        if missing:
            errors.append(
                f"Net class {net_class.name} references unknown nets: {', '.join(missing)}"
            )
    for pair in design._diff_pairs:
        missing = sorted(set(pair.nets) - available_nets)
        if missing:
            errors.append(
                f"Differential pair {pair.nets[0]}/{pair.nets[1]} references unknown nets: "
                + ", ".join(missing)
            )
        net_class = classes.get(pair.net_class)
        if net_class is None:
            errors.append(
                f"Differential pair {pair.nets[0]}/{pair.nets[1]} references "
                f"undeclared net class {pair.net_class}"
            )
        elif not set(pair.nets).issubset(net_class.nets):
            errors.append(
                f"Differential pair {pair.nets[0]}/{pair.nets[1]} is not fully assigned "
                f"to net class {pair.net_class}"
            )
    return errors
