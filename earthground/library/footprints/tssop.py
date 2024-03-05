import enum

import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class Pitch(enum.Enum):
    P0_4MM = 0.4
    P0_5MM = 0.5
    P0_65MM = 0.65


class Width(enum.Enum):
    # Part width -> pad x-center to x-center
    W3_0MM = 4.3
    W4_4MM = 5.725
    W6_1MM = 7.425
    W8_0MM = 9.325


PADS = {
    (1.1, 0.4): ap_lib.ApertureRectangle(1.1, 0.4),
    (1.475, 0.25): ap_lib.ApertureRectangle(1.475, 0.25, radius=0.0625),
    (1.475, 0.3): ap_lib.ApertureRectangle(1.475, 0.3, radius=0.075),
    (1.475, 0.4): ap_lib.ApertureRectangle(1.475, 0.4, radius=0.1),
    (1.1, 0.85): ap_lib.ApertureRectangle(1.1, 0.85),
    (1.1, 0.25): ap_lib.ApertureRectangle(1.1, 0.25),
}


class TSSOP(ft.BaseFootprint):
    def __init__(self, count: int, width: Width, pitch: Pitch, pad_size: tuple) -> None:
        aperture = PADS[pad_size]
        self.name = f"TSSOP({count})"
        self.description = (
            f"TSSOP, {count} pin, {width.value}mm width, {pitch.value}mm pitch"
        )
        self.pads = {
            i: ft.Pad(location=(x, y), aperture=aperture)
            for i, x, y in ft.get_dual_side_locations(count, width.value, pitch.value)
        }
