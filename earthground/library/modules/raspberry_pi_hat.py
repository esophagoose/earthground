import earthground.components as cmp
import earthground.library.protocols.serial as serial
import earthground.standard_values as sv
from earthground.footprints import header
from earthground.library._intent import typed_pin_map


class RaspberryPiHat(cmp.Component):
    def __init__(self):
        super().__init__()
        self.name = "RaspberryPiHat"
        pinout = {
            1: "P3V3_A",
            2: "P5V0_A",
            3: "GPIO2",
            4: "P5V0_B",
            5: "GPIO3",
            6: "GND_A",
            7: "GPIO4",
            8: "GPIO14",
            9: "GND_B",
            10: "GPIO15",
            11: "GPIO17",
            12: "GPIO18",
            13: "GPIO27",
            14: "GND_C",
            15: "GPIO22",
            16: "GPIO23",
            17: "P3V3_B",
            18: "GPIO24",
            19: "GPIO10",
            20: "GND_D",
            21: "GPIO9",
            22: "GPIO25",
            23: "GPIO11",
            24: "GPIO8",
            25: "GND_E",
            26: "GPIO7",
            27: "ID_SD",
            28: "ID_SC",
            29: "GPIO5",
            30: "GND_F",
            31: "GPIO6",
            32: "GPIO12",
            33: "GPIO13",
            34: "GND_G",
            35: "GPIO19",
            36: "GPIO16",
            37: "GPIO26",
            38: "GPIO20",
            39: "GND_H",
            40: "GPIO21",
        }
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                pinout,
                digital_bidirectional={
                    name
                    for name in pinout.values()
                    if name.startswith("GPIO") or name.startswith("ID_")
                },
                power_outputs={"P3V3_A", "P3V3_B", "P5V0_A", "P5V0_B"},
                grounds={
                    "GND_A",
                    "GND_B",
                    "GND_C",
                    "GND_D",
                    "GND_E",
                    "GND_F",
                    "GND_G",
                    "GND_H",
                },
                digital_voltage=sv.volts(0, max=3.3),
                source="Raspberry Pi 40-pin GPIO header specification",
            ),
            self,
        )
        self.uart = serial.UART(
            tx=self.pins.by_name("GPIO14"), rx=self.pins.by_name("GPIO15")
        )
        self.i2c = serial.I2C(
            sda=self.pins.by_name("GPIO2"), scl=self.pins.by_name("GPIO3")
        )
        self.footprint = header.TwoRowThroughHoleHeader(40)

    @classmethod
    def valid_gpio(cls, pin):
        return pin.name.startswith("GPIO")
