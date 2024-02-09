import common.components as cmp
import library.footprints.tssop as tssop
from library.protocols.serial import I2C

GPIO_COUNT = 16


class TCA9535PWR(cmp.Component):
    def __init__(self):
        super().__init__()
        self.name = "TCA9535PWR"
        self.detailed_description = "I/O Expander 16 I²C, SMBus 400 kHz 24-TSSOP"
        self.manufacturer = "Texas Instruments"
        self.lead_time = "6 week(s)"
        self.mpn = "TCA9535PWR"
        self.datasheet = "https://www.ti.com/general/docs/suppproductinfo.tsp?distId=10&gotoUrl=https%3A%2F%2Fwww.ti.com%2Flit%2Fgpn%2Ftca9535"
        self.description = "IC XPND 400KHZ I2C SMBUS 24TSSOP"
        self.parameters = {
            "Output Type": "Push-Pull",
            "Number of I/O": "16",
            "Operating Temperature": "-40°C ~ 85°C",
            "Voltage - Supply": "1.65V ~ 5.5V",
            "Clock Frequency": "400 kHz",
            "Interrupt Output": "Yes",
            "Supplier Device Package": "24-TSSOP",
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                21: "A0",
                2: "A1",
                3: "A2",
                12: "GND",
                1: "INT",
                4: "P00",
                5: "P01",
                6: "P02",
                7: "P03",
                8: "P04",
                9: "P05",
                10: "P06",
                11: "P07",
                13: "P10",
                14: "P11",
                15: "P12",
                16: "P13",
                17: "P14",
                18: "P15",
                19: "P16",
                20: "P17",
                22: "SCL",
                23: "SDA",
                24: "VCC",
            },
            self,
        )
        self.i2c = I2C(sda=self.pins.by_name("SDA"), scl=self.pins.by_name("SCL"))
        self.footprint = tssop.TSSOP(
            count=24,
            width=tssop.Width.W4_4MM,
            pitch=tssop.Pitch.P0_65MM,
            pad_size=(1.475, 0.4),
        )

    def gpio(self, index):
        bank = int(index / 8)
        port = index % 8
        return self.pins.by_name(f"P{bank}{port}")

    @property
    def address(self):
        address = 1 << 6
        address |= int(self.pins.by_name("A0"))
        address |= int(self.pins.by_name("A1")) << 1
        address |= int(self.pins.by_name("A2")) << 2
        return address

    @address.setter
    def address(self, value):
        assert 0 <= value <= 7, f"Invalid address {value}"
        a0 = "VCC" if value & 1 else "GND"
        a1 = "VCC" if (value >> 1) & 1 else "GND"
        a2 = "VCC" if (value >> 2) & 1 else "GND"
        self.pins.by_name("A0").net = a0
        self.pins.by_name("A1").net = a1
        self.pins.by_name("A2").ndt = a2
