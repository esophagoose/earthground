import enum

import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.footprint_types as ft
from earthground.library.protocols.serial import I2C

class JstFamily(enum.Enum):
    SH = "SH"


class JstType(enum.Enum):
    TOP_ENTRY = "BM"
    SIDE_ENTRY = "SM"


class Jst(cmp.Component):
    def __init__(self, family: JstFamily, pin_count: int):
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
                1: "1",
                2: "2",
                3: "3",
                4: "4",
                "M1": "M1",
                "M2": "M2",
            },
            self,
        )
        self.i2c = I2C(sda=self.pins.by_name("3"), scl=self.pins.by_name("4"))
        self.footprint = JstShFootprint(4, JstType.SIDE_ENTRY)


class JstShFootprint(ft.BaseFootprint):
    def __init__(self, pin_count: int, style: JstType) -> None:
        super().__init__()
        self.name = f"JST_SH_Connector_{pin_count}pin_{style.name}"
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


class JstEhFootprint(ft.BaseFootprint):
    """JST EH series 2.5mm pitch through-hole shrouded header."""

    def __init__(self, pin_count: int) -> None:
        super().__init__()
        self.name = f"JST_EH_{pin_count}pin"
        self.count = pin_count
        self.pitch = 2.5  # mm
        # JST EH: hole 0.9–1.0 mm, pad ~1.8 mm typical
        aperture = ap_lib.ApertureCircle(diameter=1.8, hole=1.0)
        x0 = -(pin_count - 1) * self.pitch / 2
        self.pads = {
            i + 1: ft.Pad([x0 + i * self.pitch, 0], aperture)
            for i in range(pin_count)
        }
        border_x1 = x0 - self.pitch
        border_x2 = x0 + pin_count * self.pitch
        border_y = 1.9
        self.silk.append([
            (border_x1, border_y),
            (border_x2, border_y),
            (border_x2, -border_y),
            (border_x1, -border_y),
            (border_x1, border_y),
        ])


class B3B_EH_A(cmp.Component):
    """JST B3B-EH-A 3-position 2.5mm pitch through-hole shrouded header (top entry)."""

    def __init__(self):
        super().__init__(refdes_prefix="J")
        self.name = "B3B-EH-A"
        self.description = "CONN HEADER 3POS 2.5MM VERT"
        self.detailed_description = "JST EH series 3-pin shrouded header, 2.5mm pitch, through-hole"
        self.manufacturer = "JST"
        self.mpn = "B3B-EH-A"
        self.datasheet = "https://www.jst.com/productSeries.php?pid=2849"
        self.parameters = {
            "Pitch": "2.5mm",
            "Positions": "3",
            "Mounting": "Through-hole",
            "Current rating": "3A",
            "Voltage rating": "250V",
            "Operating temperature": "-25°C to +85°C",
        }
        self.pins = cmp.PinContainer.from_count(3, self)
        self.footprint = JstEhFootprint(3)
