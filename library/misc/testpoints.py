import pygerber.aperture as ap_lib

import common.components as components
from library.footprints import generics


class ObroundTestpoint(components.Component):
    def __init__(self, x: float, y: float):
        super().__init__()
        self.name = f"ObroundTestpoint_{x}X{y}"
        self.refdes_prefix = "TP"
        self.pins = components.PinContainer.from_count(1, self)
        r = min([x, y]) / 2
        aperture = ap_lib.ApertureRectangle(x, y, r, r)
        self.footprint = generics.SinglePad(aperture)
