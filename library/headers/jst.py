import enum

import pygerber.layers.aperture as ap_lib

import common.components as cmp
import common.footprint_types as ft
from library.protocols.serial import I2C


class PRT_14417(cmp.Component):
    def __init__(self):
        super().__init__(refdes_prefix="J")
        self.name = "PRT-14417"
        self.detailed_description = "Qwiic - Connector"
        self.manufacturer = "SparkFun Electronics"
        self.lead_time = "6 week(s)"
        self.mpn = "PRT-14417"
        self.datasheet = ""
        self.description = "QWIIC CONNECTOR SMD 4-PIN"
        self.parameters = {
            "Packaging": "Bulk",
            "For Use With/Related Products": "Qwiic",
            "Accessory Type": "Connector",
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                1: "GND",
                2: "VCC",
                3: "SDA",
                4: "SCL",
                "M1": "MOUNTING1",
                "M2": "MOUNTING2",
            },
            self,
        )
        self.i2c = I2C(sda=self.pins.by_name("SDA"), scl=self.pins.by_name("SCL"))
        self.footprint = JstShFootprint(4, JstType.SIDE_ENTRY)


class JstType(enum.Enum):
    TOP_ENTRY = 1
    SIDE_ENTRY = 2


class JstShFootprint:
    def __init__(self, pin_count: int, style: JstType) -> None:
        self.count = pin_count
        self.style = style
        self.spacing = 1  # mm
        pad_aperture = ap_lib.ApertureRectangle(0.6, 1.55)
        mount_aperture = ap_lib.ApertureRectangle(1.2, 1.8)
        x0, y0 = self._get_pad_start()
        self.pads = {
            i + 1: ft.Pad([i + x0, y0], pad_aperture) for i in range(pin_count)
        }
        self.pads.update({"M1": ft.Pad([x0 - 1.3, 0.9], mount_aperture)})
        self.pads.update({"M2": ft.Pad([-x0 + 1.3, 0.9], mount_aperture)})

    def _get_pad_start(self):
        x = -(self.count - 1) * self.spacing / 2
        y = -3.375 if self.style == JstType.TOP_ENTRY else -4.775
        return x, y
