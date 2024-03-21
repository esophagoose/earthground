import earthground.components as cmp


AVAILABLE_PIN_CONFIGURATIONS = [4, 6, 8, 10, 16, 24, 30]


class TE_2328702(cmp.Component):
    def __init__(self, pin_count: int):
        super().__init__()
        assert pin_count in AVAILABLE_PIN_CONFIGURATIONS, "Invalid pin count"
        self.manufacturer = "TE Connectivity AMP Connectors"
        self.mpn = f"2328702-{pin_count % 10}"
        if pin_count >= 10:
            self.mpn = f"{int(pin_count / 10)}-" + self.mpn
        self.description = f"CONN FPC {pin_count}POS 0.5MM R/A"
        self.datasheet = "https://www.te.com/usa-en/product-2328702-6.datasheet.pdf"
        self.parameters = {
            "Contact Finish": "Gold",
            "Voltage Rating": "50V",
            "Current Rating (Amps)": "0.5A",
            "Mounting Type": "Surface Mount, Right Angle",
            "Number of Positions": "6",
            "Pitch": '0.020" (0.50mm)',
            "Operating Temperature": "-40°C ~ 85°C",
            "Termination": "Solder",
            "Height Above Board": '0.041" (1.05mm)',
            "Contact Finish Thickness": "3.00µin (0.076µm)",
            "Locking Feature": "Flip Lock, Backlock",
            "Material Flammability Rating": "UL94 V-0",
            "Actuator Material": "Thermoplastic",
            "Contact Material": "Copper Alloy",
            "FFC, FCB Thickness": "0.30mm",
            "Housing Material": "Thermoplastic",
            "Cable End Type": "Tapered",
            "Housing Color": "Natural",
            "Actuator Color": "Black",
            "Flat Flex Type": "FPC",
            "Connector/Contact Type": "Contacts, Top and Bottom",
        }
        self.pins = cmp.PinContainer.from_count(6, self)
