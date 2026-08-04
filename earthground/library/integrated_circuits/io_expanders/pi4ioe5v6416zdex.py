import earthground.components as cmp
import earthground.contracts as contracts
import earthground.standard_values as sv
import earthground.straps as straps
from earthground.library._intent import typed_pin_map
from earthground.library.protocols.serial import I2C
from earthground.ratings import Ratings


class PI4IOE5V6416ZDEX(cmp.Component):
    SOURCE = "PI4IOE5V6416 datasheet"
    recommended = Ratings(
        vcc=sv.volts(1.65, max=5.5, source=SOURCE),
        ta=sv.celsius(-40, max=85, source=SOURCE),
    )

    def __init__(self):
        super().__init__()
        self.name = "PI4IOE5V6416ZDEX"
        self.manufacturer = "Diodes Incorporated"
        self.mpn = "PI4IOE5V6416ZDEX"
        self.description = "IC XPNDR 400KHZ I2C 24TQFN"
        self.datasheet = "https://www.diodes.com/assets/Datasheets/PI4IOE5V6416.pdf"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.parameters = {
            "Packaging": "Cut Tape (CT)",
            "Features": "POR",
            "Package / Case": "24-VFQFN Exposed Pad",
            "Output Type": "Open Drain, Push-Pull",
            "Mounting Type": "Surface Mount",
            "Interface": "I2C",
            "Number of I/O": "16",
            "Operating Temperature": "-40°C ~ 85°C",
            "Voltage - Supply": "1.65V ~ 5.5V",
            "Clock Frequency": "400 kHz",
            "Interrupt Output": "Yes",
            "Supplier Device Package": "24-TQFN (4x4)",
            "Current - Output Source/Sink": "10mA, 25mA",
            "DigiKey Programmable": "Not Verified",
        }
        pinout = {
            "A3": "INT",  # Interrupt output. Pullup to VDD(I2C-bus) or VDD(P)
            "B3": "VDD(I2C_bus)",  # Supply voltage of I2C-bus.
            "A2": "RESET",  # Active LOW reset input
            "A1": "P0_0",  # Port 0 I/O 0
            "C3": "P0_1",  # Port 0 I/O 1
            "B1": "P0_2",  # Port 0 I/O 2
            "C1": "P0_3",  # Port 0 I/O 3
            "C2": "P0_4",  # Port 0 I/O 4
            "D1": "P0_5",  # Port 0 I/O 5
            "E1": "P0_6",  # Port 0 I/O 6
            "D2": "P0_7",  # Port 0 I/O 7
            "E2": "VSS",  # Ground
            "E3": "P1_0",  # Port 1 I/O 0
            "E4": "P1_1",  # Port 1 I/O 1
            "D3": "P1_2",  # Port 1 I/O 2
            "E5": "P1_3",  # Port 1 I/O 3
            "D4": "P1_4",  # Port 1 I/O 4
            "D5": "P1_5",  # Port 1 I/O 5
            "C5": "P1_6",  # Port 1 I/O 6
            "C4": "P1_7",  # Port 1 I/O 7
            "B5": "ADDR",  # Address input. Connect directly to VDD(P) or ground.
            "A5": "SCL",  # Serial clock bus. Connect to VDD(I2C-bus) through a pull-up resistor.
            "A4": "SDA",  # Serial data bus. Connect to VDD(I2C-bus) through a pull-up resistor.
            "B4": "VDD(P)",  # Supply voltage of PI4IOE5V6416 for Port P
        }
        gpio = {f"P{bank}_{port}" for bank in range(2) for port in range(8)}
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                pinout,
                digital_inputs={"RESET", "ADDR", "SCL"},
                digital_bidirectional=gpio,
                power_inputs={
                    "VDD(I2C_bus)": self.recommended["vcc"],
                    "VDD(P)": self.recommended["vcc"],
                },
                grounds={"VSS"},
                overrides={
                    "INT": cmp.DigitalPinSpec.output(
                        name="INT",
                        drive_style=cmp.DriveStyle.OPEN_DRAIN,
                        voltage_operating=self.recommended["vcc"],
                        source=self.SOURCE,
                    ),
                    "SDA": cmp.DigitalPinSpec.bidirectional(
                        name="SDA",
                        drive_style=cmp.DriveStyle.OPEN_DRAIN,
                        voltage_operating=self.recommended["vcc"],
                        source=self.SOURCE,
                    ),
                },
                digital_voltage=self.recommended["vcc"],
                source=self.SOURCE,
            ),
            self,
        )
        self.i2c = I2C(sda=self.pins.by_name("SDA"), scl=self.pins.by_name("SCL"))
        self.requires = (
            contracts.Decoupling(
                id="i2c-supply-decoupling",
                pin="VDD(I2C_bus)",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
            contracts.Decoupling(
                id="port-supply-decoupling",
                pin="VDD(P)",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
        )
        self.strap_pins = (
            straps.StrapPin(
                id="address",
                pin="ADDR",
                reference="VDD(P)",
                levels=(
                    straps.StrapLevel(
                        name="LOW",
                        ratio=sv.ratio(0, max=0.2),
                        meaning="low I2C address",
                    ),
                    straps.StrapLevel(
                        name="HIGH",
                        ratio=sv.ratio(0.8, max=1),
                        meaning="high I2C address",
                    ),
                ),
                sampled_on="power-up",
                source=self.SOURCE,
            ),
        )
