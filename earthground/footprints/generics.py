import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class SinglePad:
    def __init__(self, aperture: ap_lib.APERTURES) -> None:
        size = f"{aperture.width}MMx{aperture.height}MM"
        self.name = f"Single Pad, {size}"
        self.pads = {1: ft.Pad(location=(0, 0), aperture=aperture)}
