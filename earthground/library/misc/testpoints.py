import pygerber.aperture as ap_lib

import earthground.components as components
import earthground.footprints.generics as fp_lib


class ObroundTestpoint(components.Component):
    def __init__(self, x: float, y: float):
        super().__init__()
        self.name = f"ObroundTestpoint_{x}X{y}"
        self.refdes_prefix = "TP"
        self.pins = components.PinContainer.from_count(1, self)
        r = min([x, y]) / 2
        aperture = ap_lib.ApertureRectangle(x, y, r, r)
        self.footprint = fp_lib.SinglePad(aperture)


class CircleSmdTestpoint(components.Component):
    def __init__(self, diameter: float):
        super().__init__()
        self.name = f"CircleSmdTestpoint_{diameter}mm"
        self.refdes_prefix = "TP"
        self.pins = components.PinContainer.from_count(1, self)
        aperture = ap_lib.ApertureCircle(diameter)
        self.footprint = fp_lib.SinglePad(aperture)
