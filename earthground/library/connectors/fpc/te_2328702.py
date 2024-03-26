import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.footprint_types as ft

VALID_PIN_COUNTS = [4, 6, 8, 10, 16, 24, 30]


class TE_2328702(cmp.Component):
    def __init__(self, pin_count: int):
        super().__init__("J")
        assert pin_count in VALID_PIN_COUNTS, "Invalid pin count"
        self.manufacturer = "TE Connectivity AMP Connectors"
        self.mpn = f"2328702-{pin_count % 10}"
        if pin_count >= 10:
            self.mpn = f"{int(pin_count / 10)}-" + self.mpn
        self.name = f"TE {self.mpn}"
        self.description = f"CONN FPC {pin_count}POS 0.5MM R/A"
        self.datasheet = "https://www.te.com/usa-en/product-2328702-6.datasheet.pdf"
        self.parameters = {
            "Contact Finish": "Gold",
            "Voltage Rating": "50V",
            "Current Rating (Amps)": "0.5A",
            "Mounting Type": "Surface Mount, Right Angle",
            "Number of Positions": "6",
            "Pitch": '0.020" (0.50mm)',
            "Operating Temperature": "-40°C ~ 85°C",
            "Termination": "Solder",
            "Height Above Board": '0.041" (1.05mm)',
            "Contact Finish Thickness": "3.00µin (0.076µm)",
            "Locking Feature": "Flip Lock, Backlock",
            "Material Flammability Rating": "UL94 V-0",
            "Actuator Material": "Thermoplastic",
            "Contact Material": "Copper Alloy",
            "FFC, FCB Thickness": "0.30mm",
            "Housing Material": "Thermoplastic",
            "Cable End Type": "Tapered",
            "Housing Color": "Natural",
            "Actuator Color": "Black",
            "Flat Flex Type": "FPC",
            "Connector/Contact Type": "Contacts, Top and Bottom",
        }
        pins = {i: str(i) for i in range(1, pin_count + 1)}
        pins.update({"MT1": "MT1", "MT2": "MT2"})
        self.pins = cmp.PinContainer.from_dict(pins, self)
        self.footprint = TeFpcFootprint(pin_count)


class TeFpcFootprint(ft.BaseFootprint):
    def __init__(self, pin_count: int) -> None:
        self.name = f"TE_2328702_{pin_count}pos"
        self.pitch = 0.50
        height = 2.95
        width = (pin_count / 2) + 2
        cx, cy = width / 2, height / 2
        aperture = ap_lib.ApertureRectangle(0.3, 0.8)
        xstart = -(pin_count - 1) * self.pitch / 2
        y = -(height / 2) + 0.05
        self.pads = {
            i + 1: ft.Pad([xstart + i * self.pitch, y], aperture)
            for i in range(pin_count)
        }
        inner_width = width - 0.90
        mount_aperture = ap_lib.ApertureRectangle(0.4, 0.8)
        mount_x = (inner_width / 2) + (mount_aperture.width / 2)
        mount_y = cy - (mount_aperture.height / 2)
        self.pads.update({"MT1": ft.Pad([-mount_x, mount_y], mount_aperture)})
        self.pads.update({"MT2": ft.Pad([mount_x, mount_y], mount_aperture)})
        self.silk = [
            [(-cx, 0), (-cx, -cy), (xstart - aperture.width, -cy)],
            [(cx, 0), (cx, -cy), (abs(xstart) + aperture.width, -cy)],
        ]
