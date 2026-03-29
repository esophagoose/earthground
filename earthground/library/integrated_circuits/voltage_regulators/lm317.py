"""
LM317 adjustable voltage regulator component and reference design.

The LM317AMDTX is a 1A adjustable positive voltage regulator in SOT-223.
Output voltage is set by a resistor divider: Vout = 1.25 * (1 + R2/R1).
"""

import earthground.components as cmp
import earthground.footprints.sot as sot
import earthground.library.footprints.passives as passives
import earthground.schematic as sch


class LM317AMDTX(cmp.Component):
    """LM317A adjustable voltage regulator, SOT-223 package.

    Pinout (SOT-223):
        1 - ADJ (feedback)
        2 - OUT (output)
        3 - IN  (input)
        4 - OUT (tab, connected to pin 2)
    """

    def __init__(self):
        super().__init__()
        self.refdes_prefix = "REG"
        self.name = "LM317AMDTX"
        self.mpn = "LM317AMDTX/NOPB"
        self.manufacturer = "Texas Instruments"
        self.description = "IC REG LIN POS ADJ 1A SOT-223"
        self.parameters = {
            "Output Type": "Adjustable",
            "Output Current": "1A",
            "Voltage - Input": "3.7V ~ 40V",
            "Voltage - Output": "1.25V ~ 37V",
            "Operating Temperature": "-40°C ~ 125°C",
            "Package": "SOT-223",
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                1: "ADJ",
                2: "OUT",
                3: "IN",
                4: "OUT_TAB",
            },
            self,
        )
        self.footprint = sot.SOT223()

    @staticmethod
    def generate_design(vout: float, r1_ohms: int = 240) -> sch.Design:
        """Generate a complete LM317 regulator sub-design for a target voltage.

        Creates a design with:
        - LM317 regulator
        - R1 (ADJ to OUT) and R2 (ADJ to GND) to set output voltage
        - Input and output decoupling capacitors

        Resistor divider: Vout = 1.25 * (1 + R2/R1)
        => R2 = R1 * (Vout/1.25 - 1)

        :param vout: Desired output voltage in volts.
        :param r1_ohms: Value of R1 in ohms (default 240).
        :return: A Design module with ports VIN, VOUT, GND.
        """
        r2_ohms = round(r1_ohms * (vout / 1.25 - 1))

        design = sch.Design(
            f"LM317_{vout}V",
            short_name="LM317",
            ports=["VIN", "VOUT", "GND"],
        )

        reg = design.add_component(LM317AMDTX())
        r1 = cmp.Resistor(r1_ohms)
        r1.footprint = passives.PassiveSmd(passives.PassivePackage.R0805)
        r2 = cmp.Resistor(r2_ohms)
        r2.footprint = passives.PassiveSmd(passives.PassivePackage.R0805)
        cin = cmp.Capacitor("100n", 50)
        cin.footprint = passives.PassiveSmd(passives.PassivePackage.C0805)
        cout = cmp.Capacitor("1u", 10)
        cout.footprint = passives.PassiveSmd(passives.PassivePackage.C0805)
        design.add_component(r1)
        design.add_component(r2)
        design.add_component(cin)
        design.add_component(cout)

        # Input side
        design.join_net(reg.pins.by_name("IN"), "VIN")
        design.join_net(cin.pins[1], "VIN")
        design.join_net(cin.pins[2], "GND")

        # Output side - tie OUT and OUT_TAB together
        design.join_net(reg.pins.by_name("OUT"), "VOUT")
        design.join_net(reg.pins.by_name("OUT_TAB"), "VOUT")
        design.join_net(cout.pins[1], "VOUT")
        design.join_net(cout.pins[2], "GND")

        # Feedback divider: R1 from OUT to ADJ, R2 from ADJ to GND
        design.join_net(r1.pins[1], "VOUT")
        design.join_net(r1.pins[2], "ADJ_FB")
        design.join_net(reg.pins.by_name("ADJ"), "ADJ_FB")
        design.join_net(r2.pins[1], "ADJ_FB")
        design.join_net(r2.pins[2], "GND")

        # Connect ports to their nets
        design.join_net(design.port["vin"], "VIN")
        design.join_net(design.port["vout"], "VOUT")
        design.join_net(design.port["gnd"], "GND")

        return design
