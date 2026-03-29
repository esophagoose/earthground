import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class SOT23(ft.BaseFootprint):
    """SOT-23 (Small Outline Transistor) package footprint"""

    def __init__(self):
        super().__init__()
        self.name = "SOT-23"
        self.description = "SOT-23 Surface Mount Package"

        # SOT-23 pin spacing: 0.95mm between pin centers
        # Package dimensions: ~3mm x 1.75mm
        # Pin arrangement (viewed from top):
        #   2    1
        #    \  /
        #     \/
        #     3
        aperture = ap_lib.ApertureRectangle(0.8, 0.9)  # Pad size

        # Pin positions
        # Pin 1: Right side, top
        # Pin 2: Left side, top
        # Pin 3: Bottom center
        pin_spacing_x = 0.95  # mm horizontal spacing
        pin_spacing_y = 1.00  # mm vertical spacing

        self.pads = {
            1: ft.Pad(location=[-pin_spacing_x, pin_spacing_y], aperture=aperture),
            2: ft.Pad(location=[pin_spacing_x, pin_spacing_y], aperture=aperture),
            3: ft.Pad(location=[0, -pin_spacing_y], aperture=aperture),
        }


class SOT23_6(ft.BaseFootprint):
    """SOT-23-6 (Small Outline Transistor, 6-pin) package footprint."""

    def __init__(self):
        super().__init__()
        self.name = "SOT-23-6"
        self.description = "SOT-23-6 Surface Mount Package"

        # Approximate JEDEC MO-178: 0.95 mm pitch, body ~3.0 × 2.8 mm.
        aperture = ap_lib.ApertureRectangle(0.9, 0.6)

        pin_pitch = 0.95  # along the long edge
        row_offset = 1.1  # distance from center to pad row

        # Left side: pins 1 (top), 2 (mid), 3 (bottom)
        # Right side: pins 4 (bottom), 5 (mid), 6 (top)
        self.pads = {
            1: ft.Pad(location=[-row_offset, pin_pitch], aperture=aperture),
            2: ft.Pad(location=[-row_offset, 0.0], aperture=aperture),
            3: ft.Pad(location=[-row_offset, -pin_pitch], aperture=aperture),
            4: ft.Pad(location=[row_offset, -pin_pitch], aperture=aperture),
            5: ft.Pad(location=[row_offset, 0.0], aperture=aperture),
            6: ft.Pad(location=[row_offset, pin_pitch], aperture=aperture),
        }


class SC70(ft.BaseFootprint):
    """SC-70 small-outline transistor package.

    Body 2.0 mm × 1.25 mm, 0.65 mm pitch. Pins 1–2–3 on one side, 4–5 on the other.
    Ref: JEDEC MO-203, TI DCK0005A.
    """

    def __init__(self):
        super().__init__()
        self.name = "SC70"
        self.description = "SC-70 5-pin, 2.2mm body width, 0.65 mm pitch"
        pitch = 0.65  # mm
        body_width = 2.2
        aperture = ap_lib.ApertureRectangle(0.95, 0.4)
        # Left column: pins 1 (top), 2 (mid), 3 (bottom)
        # Right column: pins 4 (bottom), 5 (top)
        self.pads = {
            1: ft.Pad(location=(-body_width / 2, pitch), aperture=aperture),
            2: ft.Pad(location=(-body_width / 2, 0), aperture=aperture),
            3: ft.Pad(location=(-body_width / 2, -pitch), aperture=aperture),
            4: ft.Pad(location=(body_width / 2, -pitch), aperture=aperture),
            5: ft.Pad(location=(body_width / 2, pitch), aperture=aperture),
        }
