import earthground.components as cmp


class IQS550BLQNR(cmp.Component):
    def __init__(self):
        super().__init__()
        self.manufacturer = "Azoteq (Pty) Ltd"
        self.mpn = "IQS550BLQNR"
        self.datasheet = "https://www.azoteq.com/images/stories/pdf/iqs5xx-b000_trackpad_datasheet.pdf"
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
        self.pins = cmp.PinContainer.from_dict(pinout)
