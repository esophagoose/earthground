import enum
from typing import Tuple

import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class Width(enum.Enum):
    """
    SOIC body width options (pad center-to-center spacing)

    Narrow body: 3.9mm body width, 5.4mm pad spacing (SOIC-8, SOIC-14, SOIC-16)
    Wide body: 7.5mm body width, 7.5mm pad spacing (SOIC-20, SOIC-24, SOIC-28)
    """

    NARROW = 5.4  # Narrow body SOIC (3.9mm body width)
    WIDE = 7.5  # Wide body SOIC (7.5mm body width)


PADS = {
    (1.5, 0.6): ap_lib.ApertureRectangle(1.5, 0.6),  # Standard SOIC pad
    (1.5, 0.5): ap_lib.ApertureRectangle(1.5, 0.5),  # Narrower pad
    (1.5, 0.7): ap_lib.ApertureRectangle(1.5, 0.7),  # Wider pad
    (1.6, 0.6): ap_lib.ApertureRectangle(1.6, 0.6),  # Longer pad
    (1.4, 0.6): ap_lib.ApertureRectangle(1.4, 0.6),  # Shorter pad
}


class SOIC(ft.BaseFootprint):
    """
    Generic SOIC (Small Outline Integrated Circuit) footprint

    Supports various pin counts (8, 14, 16, 20, 24, 28, etc.) with
    standard 1.27mm pitch and selectable body width.

    Args:
        count: Number of pins (must be even, typically 8, 14, 16, 20, 24, 28)
        width: Body width option (Width.NARROW for 3.9mm, Width.WIDE for 7.5mm)
        pad_size: Tuple of (length, width) in mm for pad dimensions
    """

    def __init__(
        self,
        count: int,
        pad_size: Tuple[float, float],
        width: Width = Width.NARROW,
    ) -> None:
        super().__init__()

        if count % 2 != 0:
            raise ValueError(
                f"SOIC packages must have an even number of pins, got {count}"
            )

        if pad_size not in PADS:
            raise ValueError(
                f"Unsupported pad size {pad_size}. Supported sizes: {list(PADS.keys())}"
            )

        aperture = PADS[pad_size]
        self.name = f"SOIC-{count}_{width.name.lower()}"
        self.pitch = 1.27
        self.description = (
            f"SOIC, {count} pin, {width.name.lower()} body ({width.value}mm pad spacing), "
            f"{self.pitch}mm pitch"
        )
        self.pads = {
            i: ft.Pad(location=(x, y), aperture=aperture)
            for i, x, y in ft.get_dual_side_locations(count, width.value, self.pitch)
        }
        pin1_marker_x = self.pads[1].location[0] - aperture.width / 2 - 0.375
        pin1_marker_y = self.pads[1].location[1] - aperture.height / 2
        self.silk.append(
            [
                (pin1_marker_x, pin1_marker_y),
                (pin1_marker_x, pin1_marker_y + aperture.height),
            ]
        )
