import earthground.components as cmp
import earthground.contracts as contracts
import earthground.standard_values as sv
from earthground.library._intent import typed_pin_map
from earthground.ratings import Ratings


class LMR51606(cmp.Component):
    SOURCE = "LMR51606 datasheet"
    recommended = Ratings(
        vin=sv.volts(4, max=65, source=SOURCE),
        vout=sv.volts(0.8, max=28, source=SOURCE),
        i_out=sv.amps(min=0, max=0.6, source=SOURCE),
        tj=sv.celsius(-40, max=150, source=SOURCE),
    )

    def __init__(self):
        super().__init__()
        self.name = "LMR51606"
        self.manufacturer = "Texas Instruments"
        self.mpn = "LMR51606"
        self.description = "SIMPLE SWITCHER BUCK CONVERTER"
        self.datasheet = "https://www.ti.com/lit/ds/symlink/lmr51606.pdf?ts=1704242784728&ref_url=https%253A%252F%252Fwww.ti.com%252Fproduct%252FLMR51606"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.parameters = {
            "Package / Case": "SOT-23-6",
            "Output Type": "Adjustable",
            "Mounting Type": "Surface Mount",
            "Number of Outputs": "1",
            "Function": "Step-Down",
            "Current - Output": "600mA",
            "Operating Temperature": "-40°C ~ 150°C (TJ)",
            "Output Configuration": "Positive",
            "Frequency - Switching": "1.1MHz",
            "Topology": "Buck",
            "Supplier Device Package": "SOT-23-6",
            "Voltage - Output (Max)": "28V",
            "Voltage - Output (Min)": "0.8V",
            "Voltage - Input (Min)": "4V",
            "Voltage - Input (Max)": "65V",
        }
        pinout = {
            "1": "CB",  # Bootstrap capacitor for high-side FET driver. Connect a high quality 100-nF capacitor from this pin to the SW pin.,
            "2": "GND",  # Power ground pins. Connected to the source of low-side FET internally. Connect to system ground, ground side of CIN and COUT. The path to CIN must be as short as possible.,
            "3": "FB",  # Feedback input to the converter. Connect a resistor divider to set the output voltage. Never short this terminal to ground during operation.,
            "4": "EN",  # Precision enable input to the converter. Do not float. High = on, low = off. Can be tied to VIN. Precision enable input allows an adjustable UVLO by an external resistor divider.,
            "5": "VIN",  # Supply input pin to the internal bias LDO and high-side FET. Connect to the input supply and input bypass capacitors CIN. Input bypass capacitors must be directly connected to this pin and GND.,
            "6": "SW",  # Switching output of the converter. Internally connected to source of the high-side FET and drain of the low-side FET. Connect to the power inductor,
        }
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                pinout,
                digital_inputs={"EN"},
                analog_inputs={"FB"},
                analog_outputs={"CB"},
                power_inputs={"VIN": self.recommended["vin"]},
                power_outputs={"SW": None},
                grounds={"GND"},
                source=self.SOURCE,
            ),
            self,
        )
        self.requires = (
            contracts.Decoupling(
                id="vin-decoupling",
                pin="VIN",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
            contracts.Bypass(
                id="bootstrap-capacitor",
                pin="CB",
                return_to="SW",
                capacitance=sv.farads(min="100n", max="100n"),
                source=self.SOURCE,
            ),
        )
