import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class DGS_VSSOP(ft.BaseFootprint):
    def __init__(self, pin_count: int) -> None:
        super().__init__()
        self.name = f"DGS{str(pin_count).zfill(4)}A"
        self.body = (3.0, 2.1 * pin_count / 10 + 0.9)
        self.description = f"SOIC, {pin_count}pin, 3.0mm width, 0.5mm pitch"
        pitch = 0.5
        width = 4.4
        aperture = ap_lib.ApertureRectangle(1.45, 0.3, 0.05)
        self.pads = {
            i: ft.Pad(location=(x, y), aperture=aperture)
            for i, x, y in ft.get_dual_side_locations(pin_count, width, pitch)
        }
