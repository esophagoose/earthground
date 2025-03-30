import earthground.components as cmp


class FUSB302BVMPX(cmp.Component):
    def __init__(self):
        super().__init__()
        self.manufacturer = "onsemi"
        self.mpn = "FUSB302BVMPX"
        self.description = "IC USB CONTROLLER I2C 14WQFN"
        self.datasheet = "https://www.onsemi.com/pdf/datasheet/fusb302b-d.pdf"
        self.lcsc_part_number = "C132291"
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
        self.pins = cmp.PinContainer.from_dict(
            {
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
            },
            self,
        )
