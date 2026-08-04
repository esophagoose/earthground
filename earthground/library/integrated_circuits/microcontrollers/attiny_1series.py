import enum
import re

import earthground.components as cmp
import earthground.contracts as contracts
import earthground.standard_values as sv
from earthground.library._intent import typed_pin_map
from earthground.library.protocols import serial
from earthground.ratings import Ratings

PART_NUMBER_DECODER = r"ATTINY(\d+)(\d)(\d)-(\w{1,2})([N|F]).*"


class PackageType(enum.Enum):
    M = "VQFN"
    S = "SOIC300"
    SS = "SOIC150"


PIN_CODE_TO_PIN_COUNT = {7: 24, 6: 20, 4: 14, 2: 8}


def get_pins(package):
    if package == "SOIC8":
        return {
            1: "VDD",
            2: "PA6",
            3: "PA7",
            4: "PA1",
            5: "PA2",
            6: "PA0",
            7: "PA3",
            8: "GND",
        }
    elif package == "SOIC14":
        return {
            1: "VDD",
            2: "PA4",
            3: "PA5",
            4: "PA6",
            5: "PA7",
            6: "PB3",
            7: "PB2",
            8: "PB1",
            9: "PB0",
            10: "PA0",
            11: "PA1",
            12: "PA2",
            13: "PA3",
            14: "GND",
        }
    elif package == "SOIC20":
        return {
            1: "VDD",
            2: "PA4",
            3: "PA5",
            4: "PA6",
            5: "PA7",
            6: "PB5",
            7: "PB4",
            8: "PB3",
            9: "PB2",
            10: "PB1",
            11: "PB0",
            12: "PC0",
            13: "PC1",
            14: "PC2",
            15: "PC3",
            16: "PA0",
            17: "PA1",
            18: "PA2",
            19: "PA3",
            20: "GND",
        }
    elif package == "QFN20":
        return {
            1: "PA2",
            2: "PA3",
            3: "GND",
            4: "VDD",
            5: "PA4",
            6: "PA5",
            7: "PA6",
            8: "PA7",
            9: "PB5",
            10: "PB4",
            11: "PB3",
            12: "PB2",
            13: "PB1",
            14: "PB0",
            15: "PC0",
            16: "PC1",
            17: "PC2",
            18: "PC3",
            19: "PA0",
            20: "PA1",
        }
    elif package == "QFN24":
        return {
            1: "PA2",
            2: "PA3",
            3: "GND",
            4: "VDD",
            5: "PA4",
            6: "PA5",
            7: "PA6",
            8: "PA7",
            9: "PB7",
            10: "PB6",
            11: "PB5",
            12: "PB4",
            13: "PB3",
            14: "PB2",
            15: "PB1",
            16: "PB0",
            17: "PC0",
            18: "PC1",
            19: "PC2",
            20: "PC3",
            21: "PC4",
            22: "PC5",
            23: "PA0",
            24: "PA1",
        }
    raise ValueError(f"Unknown package: {package}")


class ATtiny(cmp.Component):
    SOURCE = "ATtiny 1-series family datasheet"
    recommended = Ratings(
        vcc=sv.volts(1.8, max=5.5, source=SOURCE),
        ta=sv.celsius(-40, max=125, source=SOURCE),
    )

    def __init__(self, part_number: str):
        super().__init__()
        part_number = part_number.upper()
        assert part_number.startswith("ATTINY")
        match = re.match(PART_NUMBER_DECODER, part_number)
        if not match:
            raise ValueError(f"Invalid part number: {part_number}")
        kb, series, pin_code, package, temp = match.groups()
        assert series == "1", "Only 1-series supported"
        self.manufacturer = "Microchip Technology"
        self.name = part_number
        self.mpn = part_number
        self.description = f"IC MCU 8BIT {kb}KB FLASH 32VQFN"
        device_name = f"ATtiny{kb}{series}{pin_code}"
        self.datasheet = f"https://www.microchip.com/en-us/product/{device_name}"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.pin_count = PIN_CODE_TO_PIN_COUNT[int(pin_code)]
        package_name = (
            f"QFN{self.pin_count}" if package == "M" else f"SOIC{self.pin_count}"
        )
        pinout = get_pins(package_name)
        gpio = {name for name in pinout.values() if name.startswith(("PA", "PB", "PC"))}
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                pinout,
                digital_bidirectional=gpio,
                power_inputs={"VDD": self.recommended["vcc"]},
                grounds={"GND"},
                digital_voltage=self.recommended["vcc"],
                source=self.SOURCE,
            ),
            self,
        )
        self.requires = (
            contracts.Decoupling(
                id="vdd-decoupling",
                pin="VDD",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
        )
        self.parameters = {
            "Program Memory Size": f"{kb}KB",
            "Operating Temperature": f"-40°C ~ {105 if temp == 'N' else 125}°C",
            "Oscillator Type": "Internal",
            "Program Memory Type": "FLASH",
            "Core Processor": "AVR",
            "Supply Voltage": "2.7V - 5.5V",
        }
        self.reset = self.pins.by_name("PA0")
        self.updi = self.pins.by_name("PA0")
        self.external_crystal = self.pins.by_name("PA3")

    @property
    def analog_pins(self):
        analog = []
        for pin in self.pins.names:
            if pin.startswith("PA") or pin.startswith("PB"):
                analog.append(pin)
        for non_apins in ["PB2", "PB3"]:
            if non_apins in analog:
                analog.remove(non_apins)
        return [self.pins.by_name(a) for a in analog]
