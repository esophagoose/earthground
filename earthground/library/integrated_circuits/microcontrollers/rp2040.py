import earthground.components as cmp
import earthground.contracts as contracts
import earthground.standard_values as sv
from earthground.library._intent import typed_pin_map
from earthground.ratings import Ratings


class RP2040(cmp.Component):
    SOURCE = "RP2040 datasheet"
    recommended = Ratings(
        vcc=sv.volts(1.8, max=3.3, source=SOURCE),
        ta=sv.celsius(-40, max=85, source=SOURCE),
    )

    def __init__(self):
        super().__init__()
        self.name = "RP2040"
        self.manufacturer = "Raspberry Pi"
        self.mpn = "SC0914(7)"
        self.description = "IC MCU 32BIT EXT MEM 56QFN"
        self.datasheet = (
            "https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf"
        )
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.parameters = {
            "Package / Case": "56-VFQFN Exposed Pad",
            "Speed": "133MHz",
            "RAM Size": "264K x 8",
            "Operating Temperature": "-40°C ~ 85°C (TC)",
            "Core Processor": "ARM® Cortex®-M0+",
            "Core Size": "32-Bit Dual-Core",
            "Voltage - Supply (Vcc/Vdd)": "1.8V ~ 3.3V",
            "Number of I/O": "30",
        }

        pinout = {
            1: "IOVDD",
            2: "GPIO0",
            3: "GPIO1",
            4: "GPIO2",
            5: "GPIO3",
            6: "GPIO4",
            7: "GPIO5",
            8: "GPIO6",
            9: "GPIO7",
            10: "IOVDD",
            11: "GPIO8",
            12: "GPIO9",
            13: "GPIO10",
            14: "GPIO11",
            15: "GPIO12",
            16: "GPIO13",
            17: "GPIO14",
            18: "GPIO15",
            19: "XIN",
            20: "XOUT",
            21: "TESTEN",
            22: "IOVDD",
            23: "DVDD",
            24: "SWCLK",
            25: "SWDIO",
            26: "RUN",
            27: "GPIO16",
            28: "GPIO17",
            29: "GPIO18",
            30: "GPIO19",
            31: "GPIO20",
            32: "GPIO21",
            33: "IOVDD",
            34: "GPIO22",
            35: "GPIO23",
            36: "GPIO24",
            37: "GPIO25",
            38: "GPIO26/ADC0",
            39: "GPIO27/ADC1",
            40: "GPIO28/ADC2",
            41: "GPIO29/ADC3",
            42: "IOVDD",
            43: "ADC_AVDD",
            44: "VREG_VIN",
            45: "VREG_VOUT",
            46: "USB_DM",
            47: "USB_DP",
            48: "USB_VDD",
            49: "IOVDD",
            50: "DVDD",
            51: "QSPI_SD3",
            52: "QSPI_SCLK",
            53: "QSPI_SD0",
            54: "QSPI_SD2",
            55: "QSPI_SD1",
            56: "QSPI_SS_N",
            57: "EPAD",
        }
        gpio = {name for name in pinout.values() if name.startswith("GPIO")}
        overrides = {
            "USB_DP": cmp.AnalogPinSpec(
                name="USB_DP",
                direction=cmp.PinDirection.BIDIRECTIONAL,
                interface=cmp.PinInterfaceRef(
                    interface="usb", polarity=cmp.DifferentialPolarity.POSITIVE
                ),
                source=self.SOURCE,
            ),
            "USB_DM": cmp.AnalogPinSpec(
                name="USB_DM",
                direction=cmp.PinDirection.BIDIRECTIONAL,
                interface=cmp.PinInterfaceRef(
                    interface="usb", polarity=cmp.DifferentialPolarity.NEGATIVE
                ),
                source=self.SOURCE,
            ),
        }
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                pinout,
                digital_inputs={"TESTEN", "SWCLK", "RUN"},
                digital_outputs={"QSPI_SCLK", "QSPI_SS_N"},
                digital_bidirectional=gpio
                | {"SWDIO", "QSPI_SD0", "QSPI_SD1", "QSPI_SD2", "QSPI_SD3"},
                analog_inputs={"XIN"},
                analog_outputs={"XOUT"},
                power_inputs={
                    "IOVDD": self.recommended["vcc"],
                    "ADC_AVDD": self.recommended["vcc"],
                    "VREG_VIN": self.recommended["vcc"],
                    "USB_VDD": self.recommended["vcc"],
                },
                power_outputs={
                    "DVDD": sv.volts(typ=1.1, source=self.SOURCE),
                    "VREG_VOUT": sv.volts(typ=1.1, source=self.SOURCE),
                },
                grounds={"EPAD"},
                overrides=overrides,
                digital_voltage=self.recommended["vcc"],
                source=self.SOURCE,
            ),
            self,
        )
        self.interfaces = {
            "usb": cmp.DifferentialInterfaceSpec(
                name="usb",
                positive="USB_DP",
                negative="USB_DM",
                target_impedance=sv.ohms(typ=90, source=self.SOURCE),
            )
        }
        self.requires = (
            contracts.Decoupling(
                id="iovdd-decoupling",
                pin="IOVDD",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                per_pin=True,
                source=self.SOURCE,
            ),
            contracts.Decoupling(
                id="dvdd-decoupling",
                pin="DVDD",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                per_pin=True,
                source=self.SOURCE,
            ),
            contracts.Decoupling(
                id="vreg-output-decoupling",
                pin="VREG_VOUT",
                capacitance=sv.farads(min="1u", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
        )
