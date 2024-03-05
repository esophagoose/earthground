import re

import earthground.components as cmp
from earthground.library.footprints import header
from earthground.library.protocols.serial import I2C, UART

ANALOG_PINS = ["A0", "A1", "A4", "A6", "A7", "B0", "B1"]


class BlackPill(cmp.Component):
    def __init__(self):
        super().__init__()
        self.name = "BlackPillV2"
        self.pins = cmp.PinContainer.from_dict(
            {
                1: "B12",
                2: "B13",
                3: "B14",
                4: "B15",
                5: "A8",
                6: "A9",
                7: "A10",
                8: "A11",
                9: "A12",
                10: "A15",
                11: "B3",
                12: "B4",
                13: "B5",
                14: "B6",
                15: "B7",
                16: "B8",
                17: "B9",
                18: "P5V0_1",
                19: "GND_1",
                20: "P3V3",
                21: "P5V0_2",
                22: "GND_2",
                23: "P3V3",
                24: "B10",
                25: "B2",
                26: "B1",
                27: "B0",
                28: "A7",
                29: "A6",
                30: "A5",
                31: "A4",
                32: "A3",
                33: "A2",
                34: "A1",
                35: "A0",
                36: "NRST",
                37: "C15",
                38: "C14",
                39: "C13",
                40: "VBAT",
            },
            self,
        )

        self.uart = [
            UART(tx=self.pins.by_name("A15"), rx=self.pins.by_name("B3")),
            UART(tx=self.pins.by_name("A2"), rx=self.pins.by_name("A3")),
            UART(tx=self.pins.by_name("A2"), rx=self.pins.by_name("A3")),
        ]

        self.i2c = [
            I2C(sda=self.pins.by_name("B7"), scl=self.pins.by_name("B6")),
            I2C(sda=self.pins.by_name("B3"), scl=self.pins.by_name("B10")),
            I2C(sda=self.pins.by_name("B4"), scl=self.pins.by_name("A8")),
        ]

        self.footprint = header.TwoRowThroughHoleHeader(40, 100)

    @classmethod
    def valid_gpio(cls, name):
        pattern = r"^[A-Z]\d+$"
        return bool(re.match(pattern, name))
