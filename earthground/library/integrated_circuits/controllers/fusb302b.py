import earthground.components as cmp
import earthground.contracts as contracts
import earthground.standard_values as sv
from earthground.library._intent import typed_pin_map
from earthground.library.protocols.serial import I2C
from earthground.ratings import Ratings


class FUSB302BVMPX(cmp.Component):
    SOURCE = "FUSB302B datasheet"
    recommended = Ratings(
        vbus=sv.volts(4, max=21, source=SOURCE),
        ta=sv.celsius(-40, max=105, source=SOURCE),
    )

    def __init__(self):
        super().__init__()
        self.name = "FUSB302BVMPX"
        self.manufacturer = "onsemi"
        self.mpn = "FUSB302BVMPX"
        self.description = "IC USB CONTROLLER I2C 14WQFN"
        self.datasheet = "https://www.onsemi.com/pdf/datasheet/fusb302b-d.pdf"
        self.datasheet_revision = "FUSB302B/D"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.distributor_ids["lcsc"] = "C132291"
        self.parameters = {
            "Package / Case": "14-WFQFN Exposed Pad",
            "Interface": "I2C",
            "Operating Temperature": "-40°C ~ 105°C (TA)",
            "Voltage - Supply": "4V ~ 21V",
            "Current - Supply": "560mA",
            "Protocol": "USB",
            "Standards": "USB 3.1",
            "Supplier Device Package": "14-WQFN (2.5x2.5)",
            "Grade": "Automotive",
            "Qualification": "AEC-Q100",
        }
        pinout = {
            "1": "CC2",
            "2": "VBUS",
            "3": "VDD",
            "4": "VDD",
            "5": "INT_N",
            "6": "SCL",
            "7": "SDA",
            "8": "GND",
            "9": "GND",
            "10": "CC1",
            "11": "CC1",
            "12": "VCONN",
            "13": "VCONN",
            "14": "CC2",
        }
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                pinout,
                digital_inputs={"SCL"},
                power_inputs={"VBUS": self.recommended["vbus"], "VDD": None},
                power_outputs={"VCONN": None},
                grounds={"GND"},
                analog_inputs={"CC1", "CC2"},
                overrides={
                    "INT_N": cmp.DigitalPinSpec.output(
                        name="INT_N",
                        drive_style=cmp.DriveStyle.OPEN_DRAIN,
                        source=self.SOURCE,
                    ),
                    "SDA": cmp.DigitalPinSpec.bidirectional(
                        name="SDA",
                        drive_style=cmp.DriveStyle.OPEN_DRAIN,
                        source=self.SOURCE,
                    ),
                },
                source=self.SOURCE,
            ),
            self,
        )
        self.i2c = I2C(sda=self.pins.by_name("SDA"), scl=self.pins.by_name("SCL"))
        self.requires = (
            contracts.Decoupling(
                id="vdd-decoupling",
                pin="VDD",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
        )
