import enum

import earthground.components as cmp
import earthground.standard_values as sv
from earthground.library.integrated_circuits.microcontrollers.atmega16u2_mur import (
    ATMEGA16U2_MU,
)


class Package(enum.Enum):
    QFN = "MU"
    TSSOP = "AU"


class ATMEGA16U2(ATMEGA16U2_MU):
    def __init__(self, package: Package):
        super().__init__()
        self.name = "ATMEGA16U2"
        self.detailed_description = "AVR AVR® ATmega Microcontroller IC 8-Bit 16MHz 16KB (8K x 16) FLASH 32-TQFP (7x7)"
        self.manufacturer = "Microchip Technology"
        self.lead_time = sv.weeks(typ=18)
        self.mpn = "ATMEGA16U2-" + package.value
        self.datasheet = "https://ww1.microchip.com/downloads/en/DeviceDoc/7799S.pdf"
        self.description = "IC MCU 8BIT 16KB FLASH 32TQFP"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
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
