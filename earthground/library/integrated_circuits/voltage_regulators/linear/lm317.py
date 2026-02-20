import earthground.components as cmp
import earthground.layout as layout_lib
import earthground.footprints.transistor_outline as to
import earthground.schematic as sch
import earthground.standard_values as sv


class LM317AMDTX(cmp.Component):
    """LM317AMDTX Adjustable Positive Voltage Regulator"""

    def __init__(self):
        super().__init__()
        self.name = "LM317AMDTX"
        self.detailed_description = (
            "Adjustable Positive Voltage Regulator, 1.5A, TO-252-3"
        )
        self.manufacturer = "Texas Instruments"
        self.mpn = "LM317AMDTX"
        self.datasheet = "https://www.ti.com/lit/ds/snvs774k/snvs774k.pdf"
        self.description = "IC REG LINEAR POS ADJ 1.5A TO252"
        self.parameters = {
            "Package / Case": "TO-252-3 (DPAK)",
            "Mounting Type": "Surface Mount",
            "Output Type": "Adjustable",
            "Number of Regulators": "1",
            "Voltage - Input (Max)": "40V",
            "Voltage - Output (Min/Fixed)": "1.25V",
            "Voltage - Output (Max)": "37V",
            "Current - Output": "1.5A",
            "Line Regulation": "0.01% / V",
            "Load Regulation": "0.3%",
            "Operating Temperature": "-40°C ~ 125°C",
        }
        # TO-252-3 pinout:
        # Pin 1: ADJ (Adjust)
        # Pin 2: VOUT (Output) - also tab
        # Pin 3: VIN (Input)
        self.pins = cmp.PinContainer.from_dict(
            {
                1: "ADJ",
                2: "VOUT",
                3: "VIN",
            },
            self,
        )
        self.footprint = to.TO252()
        self._output_voltage = None

    def get_adj_resistors(self, output_voltage: float):
        """
        Calculate the resistor values for the adjustment network.

        Formula: Vout = 1.25V * (1 + R2/R1) + Iadj * R2
        Typically Iadj is negligible (~50µA), so: Vout ≈ 1.25V * (1 + R2/R1)
        Rearranging: R2/R1 = (Vout/1.25V) - 1

        Args:
            output_voltage: Desired output voltage in volts

        Returns:
            Tuple of (R1, R2) Resistor objects
        """
        self._output_voltage = output_voltage
        # Vref = 1.25V for LM317
        vref = 1.25
        # Calculate ratio R2/R1
        ratio = (output_voltage / vref) - 1
        # Find closest standard resistor values
        r1_value, r2_value = sv.find_closest_ratio(ratio)
        # Use 240Ω as a common R1 value for stability (datasheet recommends 120-240Ω)
        # But we'll use the calculated value
        r1 = cmp.Resistor(f"{r1_value}k")
        r2 = cmp.Resistor(f"{r2_value}k")
        return r1, r2

    def validate(self):
        """Validate that the output voltage is within acceptable range"""
        if self._output_voltage is not None:
            assert (
                1.25 <= self._output_voltage <= 37
            ), f"Vout {self._output_voltage}V out of range (1.25V - 37V)"

    @classmethod
    def generate_design(
        cls,
        output_voltage: float,
        input_voltage_net: str = "VIN",
        output_net: str = "VOUT",
        design_name: str = "LM317AMDTX_Regulator",
    ):
        """
        Generate a reference design for LM317AMDTX regulator.

        Args:
            output_voltage: Desired output voltage in volts
            input_voltage_net: Name of the input voltage net
            output_net: Name of the output voltage net
            design_name: Name for the design

        Returns:
            Design object with the regulator circuit
        """
        design = sch.Design(design_name, "REG", ports=["VIN", "VOUT", "GND"])
        ldo = cls()
        placed_ldo = design.add_component(ldo)

        # Input decoupling capacitor (recommended: 0.1µF to 1µF)
        input_cap = cmp.Capacitor("1u", 50)
        design.add_component(input_cap)
        design.join_net(placed_ldo.pins.by_name("VIN"), input_voltage_net)
        design.join_net(input_cap.pins[1], input_voltage_net)
        design.join_net(input_cap.pins[2], "GND")

        # Output decoupling capacitor (recommended: 1µF to 10µF)
        output_cap = cmp.Capacitor("10u", 25)
        design.add_component(output_cap)
        design.join_net(placed_ldo.pins.by_name("VOUT"), output_net)
        design.join_net(output_cap.pins[1], output_net)
        design.join_net(output_cap.pins[2], "GND")

        # Adjustment resistor network
        r1, r2 = ldo.get_adj_resistors(output_voltage)
        placed_r1 = design.add_component(r1)
        placed_r2 = design.add_component(r2)

        # Connect R1 between VOUT and ADJ
        design.connect([placed_ldo.pins.by_name("VOUT"), placed_r1.pins[1]], output_net)
        design.connect(
            [placed_ldo.pins.by_name("ADJ"), placed_r1.pins[2], placed_r2.pins[1]],
            "ADJ_NET",
        )

        # Connect R2 between ADJ and GND
        design.connect([placed_r2.pins[2]], "GND")

        # Connect power pins
        design.connect([placed_ldo.pins.by_name("VIN")], input_voltage_net)
        design.connect([placed_ldo.pins.by_name("VOUT")], output_net)

        # Connect ports to component pins
        design.join_net(design.port["VIN"], input_voltage_net)
        design.join_net(design.port["VOUT"], output_net)
        design.join_net(design.port["GND"], "GND")
        design.layout.placement = {
            "C1": layout_lib.ComponentLayout(
                id=layout_lib.Position(x=0.0, y=-1.5, angle=0.0),
                component=layout_lib.Position(x=3.55, y=-4.5, angle=0.0),
            ),
            "C2": layout_lib.ComponentLayout(
                id=layout_lib.Position(x=-2.775, y=0.0, angle=0.0),
                component=layout_lib.Position(x=-4.225, y=4.5, angle=180.0),
            ),
            "R1": layout_lib.ComponentLayout(
                id=layout_lib.Position(x=0.0, y=1.5, angle=0.0),
                component=layout_lib.Position(x=-4.45, y=-4.5, angle=180.0),
            ),
            "R2": layout_lib.ComponentLayout(
                id=layout_lib.Position(x=0.0, y=1.5, angle=0.0),
                component=layout_lib.Position(x=-0.45, y=-4.5, angle=180.0),
            ),
            "U1": layout_lib.ComponentLayout(
                id=layout_lib.Position(x=-4.455, y=0.0, angle=0.0),
                component=layout_lib.Position(x=0.0, y=0.0, angle=0.0),
            ),
            "REG1": layout_lib.ComponentLayout(
                component=layout_lib.Position(x=0.0, y=20.0, angle=0.0),
            ),
        }
        return design


if __name__ == "__main__":
    import earthground.exporters.kicad as kicad

    design = LM317AMDTX.generate_design(3.3)
    design.add_module(LM317AMDTX.generate_design(3.3))
    kicad.KicadExporter(design).save()
