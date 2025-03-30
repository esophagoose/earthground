import enum

import earthground.components as cmp


class Package(enum.Enum):
    QFN = "MU"
    TSSOP = "AU"


class ATMEGA16U2(cmp.Component):
    def __init__(self, package: Package):
        super().__init__()
        self.name = "ATMEGA16U2"
        self.detailed_description = "AVR AVR® ATmega Microcontroller IC 8-Bit 16MHz 16KB (8K x 16) FLASH 32-TQFP (7x7)"
        self.manufacturer = "Microchip Technology"
        self.lead_time = "18 week(s)"
        self.mpn = "ATMEGA16U2-" + package.value
        self.datasheet = "https://ww1.microchip.com/downloads/en/DeviceDoc/7799S.pdf"
        self.description = "IC MCU 8BIT 16KB FLASH 32TQFP"
        self.parameters = {
            "Packaging": "Tray",
            "Package / Case": "32-TQFP",
            "Mounting Type": "Surface Mount",
            "Speed": "16MHz",
            "Program Memory Size": "16KB (8K x 16)",
            "RAM Size": "512 x 8",
            "Operating Temperature": "-40°C ~ 85°C (TA)",
            "Oscillator Type": "Internal",
            "Program Memory Type": "FLASH",
            "EEPROM Size": "512 x 8",
            "Core Processor": "AVR",
            "Data Converters": "-",
            "Core Size": "8-Bit",
            "Voltage - Supply (Vcc/Vdd)": "2.7V ~ 5.5V",
            "Connectivity": "SPI, UART/USART, USB",
            "Peripherals": "Brown-out Detect/Reset, POR, PWM, WDT",
            "Supplier Device Package": "32-TQFP (7x7)",
            "Number of I/O": "22",
            "DigiKey Programmable": "Verified",
        }
