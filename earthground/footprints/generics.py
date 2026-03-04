import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class SinglePad(ft.BaseFootprint):
    def __init__(self, aperture: ap_lib.APERTURES) -> None:
        super().__init__()
        self.name = f"Single Pad, {aperture} (mm)"
        self.pads = {1: ft.Pad(location=(0, 0), aperture=aperture)}
