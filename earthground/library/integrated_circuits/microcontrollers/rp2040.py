import earthground.components as cmp


class RP2040(cmp.Component):
    def __init__(self):
        super().__init__()
        self.manufacturer = "Raspberry Pi"
        self.mpn = "SC0914(7)"
        self.description = "IC MCU 32BIT EXT MEM 56QFN"
        self.datasheet = (
            "https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf"
        )
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

        self.pins = cmp.PinContainer.from_dict(
            {
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
            },
            self,
        )
