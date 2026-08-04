import earthground.components as cmp
import earthground.contracts as contracts
import earthground.standard_values as sv
from earthground.library._intent import typed_pin_map
from earthground.library.protocols.serial import I2C
from earthground.ratings import Ratings


class IQS550BLQNR(cmp.Component):
    SOURCE = "IQS5xx-B000 trackpad datasheet"
    recommended = Ratings(
        vcc=sv.volts(1.65, max=3.6, source=SOURCE),
        ta=sv.celsius(-40, max=85, source=SOURCE),
    )

    def __init__(self):
        super().__init__()
        self.name = "IQS550BLQNR"
        self.manufacturer = "Azoteq (Pty) Ltd"
        self.mpn = "IQS550BLQNR"
        self.datasheet = "https://www.azoteq.com/images/stories/pdf/iqs5xx-b000_trackpad_datasheet.pdf"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.description = "150CH. TRACKPAD/TOUCH SCREEN CON"
        self.parameters = {
            "Package / Case": "48-UFQFN Exposed Pad",
            "Interface": "I2C",
            "Operating Temperature": "-40°C ~ 85°C",
            "Voltage - Supply": "1.65V ~ 3.6V",
            "Current - Supply": "80mA",
            "Number of Inputs": "150",
            "Supplier Device Package": "48-QFN (7x7)",
            "Proximity Detection": "Yes",
        }
        pinout = {33 + i: f"TX{i}" for i in range(14)}
        pinout.update({1: "TX14"})
        for i in range(0, 20, 2):
            pinout.update({13 + i: f"RX{i}A"})
            pinout.update({14 + i: f"RX{i}B"})
        pinout.update(
            {
                2: "PGM",
                3: "SW_IN",
                4: "NC",
                5: "SDA",
                6: "SCL",
                7: "VDDHI",
                8: "VSS",
                9: "VREG",
                10: "NRST",
                11: "RDY",
                12: "NC",
                37: "VSSIO",
                38: "VDDIO",
                49: "TAB",
            }
        )
        overrides = {
            "SDA": cmp.DigitalPinSpec.bidirectional(
                name="SDA",
                drive_style=cmp.DriveStyle.OPEN_DRAIN,
                voltage_operating=self.recommended["vcc"],
                source=self.SOURCE,
            )
        }
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                pinout,
                digital_inputs={"PGM", "SW_IN", "SCL", "NRST"},
                digital_outputs={"RDY"},
                analog_inputs={
                    name for name in pinout.values() if name.startswith("RX")
                },
                analog_outputs={
                    name for name in pinout.values() if name.startswith("TX")
                },
                power_inputs={
                    "VDDHI": self.recommended["vcc"],
                    "VDDIO": self.recommended["vcc"],
                },
                power_outputs={"VREG": None},
                grounds={"VSS", "VSSIO", "TAB"},
                no_connects={"NC"},
                overrides=overrides,
                digital_voltage=self.recommended["vcc"],
                source=self.SOURCE,
            ),
            self,
        )
        self.i2c = I2C(sda=self.pins.by_name("SDA"), scl=self.pins.by_name("SCL"))
        self.requires = (
            contracts.Decoupling(
                id="vddhi-decoupling",
                pin="VDDHI",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
            contracts.Decoupling(
                id="vddio-decoupling",
                pin="VDDIO",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
        )
