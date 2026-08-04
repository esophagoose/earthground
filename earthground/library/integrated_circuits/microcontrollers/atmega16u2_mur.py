import earthground.components as cmp
import earthground.contracts as contracts
import earthground.standard_values as sv
from earthground.library._intent import typed_pin_map
from earthground.library.protocols import serial
from earthground.ratings import Ratings


class ATMEGA16U2_MU(cmp.Component):
    SOURCE = "ATmega16U2 datasheet doc7799"
    recommended = Ratings(
        vcc=sv.volts(2.7, max=5.5, source=SOURCE),
        ta=sv.celsius(-40, max=85, source=SOURCE),
    )

    def __init__(self):
        super().__init__()
        self.detailed_description = "AVR AVR® ATmega Microcontroller IC 8-Bit 16MHz 16KB (8K x 16) FLASH 32-VQFN (5x5)"
        self.manufacturer = "Microchip Technology"
        self.name = "ATMEGA16U2-MU"
        self.lead_time = sv.weeks(typ=29)
        self.mpn = "ATMEGA16U2-MU"
        self.datasheet = "https://ww1.microchip.com/downloads/en/DeviceDoc/doc7799.pdf"
        self.datasheet_revision = "doc7799"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.description = "IC MCU 8BIT 16KB FLASH 32VQFN"
        self.parameters = {
            "Package / Case": "32-VFQFN Exposed Pad",
            "Speed": "16MHz",
            "Program Memory Size": "16KB (8K x 16)",
            "RAM Size": "512 x 8",
            "Operating Temperature": "-40°C - 85°C",
            "Oscillator Type": "Internal",
            "Program Memory Type": "FLASH",
            "EEPROM Size": "512 x 8",
            "Core Processor": "AVR",
            "Supply Voltage": "2.7V - 5.5V",
            "Connectivity": "SPI, UART/USART, USB",
            "Number of I/O": "22",
        }
        pinout = {
            4: "VCC",
            3: "GND",
            32: "AVCC",  # Analog supply voltage; connect through RC to VCC
            14: "PB0",  # nSS, PCINT0
            15: "PB1",  # SCLK, PCINT1
            16: "PB2",  # MOSI, PCINT2
            17: "PB3",  # MISO, PCINT3, PDO
            18: "PB4",  # TIMER1, PCINT4
            19: "PB5",  # PCINT5
            20: "PB6",  # PCINT6
            21: "PB7",  # PCINT7, OC.0A, OC.1C
            5: "PC2",  # AIN2, PCINT11
            22: "PC7",  # INT4, ICP1, CLKO
            23: "PC6",  # PCINT8, OC.1A
            25: "PC5",  # PCINT9, OC.1B
            26: "PC4",  # PCINT10
            6: "PD0",  # INT0, OC.0B
            7: "PD1",  # AIN0, INT1
            8: "PD2",  # RXD1, AIN1, INT2
            9: "PD3",  # TXD1, INT3
            10: "PD4",  # INT5, AIN3
            11: "PD5",  # XCK, AIN4, PCINT12
            12: "PD6",  # nRTS, AIN5, INT6
            13: "PD7",  # nCTS, nHWB, AIN6, T0, INT7
            30: "D-",  # USB Full Speed Negative Data
            29: "D+",  # USB Full Speed Positive Data
            28: "UGND",  # USB Ground
            31: "UVCC",  # USB supply voltage
            27: "UCAP",  # USB supply voltage decoupling cap (1uf)
            24: "RESET/PC1/dW",  # Reset, active low
            1: "XTAL1",
            2: "PC0",  # XTAL2
        }
        gpio = {
            name
            for name in pinout.values()
            if name.startswith(("PB", "PC", "PD", "RESET/"))
        }
        overrides = {
            "D+": cmp.AnalogPinSpec(
                name="D+",
                direction=cmp.PinDirection.BIDIRECTIONAL,
                interface=cmp.PinInterfaceRef(
                    interface="usb", polarity=cmp.DifferentialPolarity.POSITIVE
                ),
                source=self.SOURCE,
            ),
            "D-": cmp.AnalogPinSpec(
                name="D-",
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
                digital_bidirectional=gpio,
                analog_inputs={"XTAL1"},
                power_inputs={
                    "VCC": self.recommended["vcc"],
                    "AVCC": self.recommended["vcc"],
                    "UVCC": self.recommended["vcc"],
                },
                power_outputs={"UCAP": None},
                grounds={"GND", "UGND"},
                overrides=overrides,
                digital_voltage=self.recommended["vcc"],
                source=self.SOURCE,
            ),
            self,
        )
        self.interfaces = {
            "usb": cmp.DifferentialInterfaceSpec(
                name="usb",
                positive="D+",
                negative="D-",
                target_impedance=sv.ohms(typ=90, source=self.SOURCE),
            )
        }
        self.requires = (
            *(
                contracts.Decoupling(
                    id=f"{pin.lower()}-decoupling",
                    pin=pin,
                    capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                    source=self.SOURCE,
                )
                for pin in ("VCC", "AVCC", "UVCC")
            ),
            contracts.Decoupling(
                id="ucap-decoupling",
                pin="UCAP",
                capacitance=sv.farads(min="1u", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
        )

        ains = ["PD1", "PD2", "PD4", "PD5", "PD6", "PD7"]
        self.analog_in = [self.pins.by_name(a) for a in ains]
        self.uart = serial.UART(
            rx=self.pins.by_name("PD2"), tx=self.pins.by_name("PD3")
        )
        self.spi = serial.SPI(
            mosi=self.pins.by_name("PB2"),
            miso=self.pins.by_name("PB3"),
            sck=self.pins.by_name("PB1"),
            cs=self.pins.by_name("PB0"),
        )
