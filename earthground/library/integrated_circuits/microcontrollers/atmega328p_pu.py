import earthground.components as cmp
import earthground.contracts as contracts
import earthground.standard_values as sv
from earthground.library._intent import typed_pin_map
from earthground.library.protocols import serial
from earthground.ratings import Ratings


class ATMEGA328P_PU(cmp.Component):
    SOURCE = "ATmega328P datasheet DS40002061B"
    recommended = Ratings(
        vcc=sv.volts(1.8, max=5.5, source=SOURCE),
        ta=sv.celsius(-40, max=85, source=SOURCE),
    )

    def __init__(self):
        super().__init__()
        self.detailed_description = "AVR AVR® ATmega Microcontroller IC 8-Bit 20MHz 32KB (16K x 16) FLASH 28-PDIP"
        self.manufacturer = "Microchip Technology"
        self.name = "ATMEGA328P-PU"
        self.mpn = "ATMEGA328P-PU"
        self.datasheet = "https://ww1.microchip.com/downloads/en/DeviceDoc/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf"
        self.datasheet_revision = "DS40002061B"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.description = "IC MCU 8BIT 32KB FLASH 28DIP"
        self.parameters = {
            "Package / Case": '28-DIP (0.300", 7.62mm)',
            "Mounting Type": "Through Hole",
            "Speed": "20MHz",
            "Program Memory Size": "32KB (16K x 16)",
            "RAM Size": "2K x 8",
            "Operating Temperature": "-40°C ~ 85°C",
            "Oscillator Type": "Internal",
            "Program Memory Type": "FLASH",
            "EEPROM Size": "1K x 8",
            "Core Processor": "AVR",
            "Data Converters": "A/D 6x10b",
            "Core Size": "8-Bit",
            "Supply Voltage": "1.8V ~ 5.5V",
            "Connectivity": "I2C, SPI, UART/USART",
            "Supplier Device Package": "28-PDIP",
            "Number of I/O": "23",
        }
        pinout = {
            28: "PC5",  # ADC5
            27: "PC4",  # ADC4
            26: "PC3",  # ADC3
            25: "PC2",  # ADC2
            24: "PC1",  # ADC1
            23: "PC0",  # ADC0
            19: "PB5",  # SCK
            18: "PB4",  # MISO
            17: "PB3",  # MOSI
            16: "PB2",  # SS
            15: "PB1",  # OC1
            14: "PB0",  # ICP
            13: "PD7",  # AIN1
            12: "PD6",  # AIN0
            11: "PD5",  # T1
            6: "PD4",  # T0
            5: "PD3",  # INT1
            4: "PD2",  # INT0
            3: "PD1",  # TXD
            2: "PD0",  # RXD
            8: "GND",
            7: "VCC",
            20: "AVCC",
            21: "AREF",
            22: "GND",
            9: "XTAL1",
            10: "XTAL2",
            1: "PC6",  # RESET
        }
        gpio = {name for name in pinout.values() if name.startswith(("PB", "PC", "PD"))}
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                pinout,
                digital_bidirectional=gpio,
                analog_inputs={"AREF", "XTAL1"},
                analog_outputs={"XTAL2"},
                power_inputs={
                    "VCC": self.recommended["vcc"],
                    "AVCC": self.recommended["vcc"],
                },
                grounds={"GND"},
                digital_voltage=self.recommended["vcc"],
                source=self.SOURCE,
            ),
            self,
        )
        self.requires = (
            contracts.Decoupling(
                id="vcc-decoupling",
                pin="VCC",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
            contracts.Decoupling(
                id="avcc-decoupling",
                pin="AVCC",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
        )

        ains = [f"PC{index}" for index in range(6)]
        self.analog_in = [self.pins.by_name(a) for a in ains]
        self.uart = serial.UART(
            rx=self.pins.by_name("PD0"), tx=self.pins.by_name("PD1")
        )
        self.spi = serial.SPI(
            mosi=self.pins.by_name("PB3"),
            miso=self.pins.by_name("PB4"),
            sck=self.pins.by_name("PB5"),
            cs=self.pins.by_name("PB2"),
        )
