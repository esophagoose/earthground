"""SOT (Small Outline Transistor) package footprints."""

import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class SOT223(ft.BaseFootprint):
    """SOT-223 (JEDEC TO-261) footprint.

    4-pin package: 3 small pads on one side, 1 large tab pad on the other.
    Commonly used for voltage regulators (LM317, AMS1117, etc.).
    """

    def __init__(self) -> None:
        super().__init__()
        self.name = "SOT-223"
        self.description = "SOT-223 (TO-261), 2.3mm pitch"

        pitch = 2.3  # mm between small pads
        width = 3.5  # mm center-to-center across the package (small to tab)

        small_pad = ap_lib.ApertureRectangle(1.2, 0.7)
        tab_pad = ap_lib.ApertureRectangle(1.2, 3.2)

        # Pins 1-3: small pads on the bottom side
        self.pads = {
            1: ft.Pad(location=[-width / 2, -pitch], aperture=small_pad),
            2: ft.Pad(location=[-width / 2, 0], aperture=small_pad),
            3: ft.Pad(location=[-width / 2, pitch], aperture=small_pad),
            # Pin 4: large tab pad on the top side
            4: ft.Pad(location=[width / 2, 0], aperture=tab_pad),
        }
