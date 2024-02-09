import common.components as cmp
import common.schematic as schematic
import common.standard_values as sv


class AP7330(cmp.Component):
    def __init__(self):
        super().__init__()
        self.name = "AP7330"
        self.pins = cmp.PinContainer.from_dict(
            {1: "VIN", 2: "GND", 3: "EN", 4: "ADJ", 5: "VOUT"}, self
        )
        self._output_voltage = None

    def get_adj_resistors(self, output_voltage):
        # Datasheet: R2 < 10k to maintain the stability
        # Datasheet: Vref = 0.8V
        # Datasheet: R1 = R2((Vout/Vref) - 1)
        self._output_voltage = output_voltage
        ratio = (output_voltage / 0.8) - 1  # Assume R2 = 1
        r1, r2 = sv.find_closest_ratio(ratio)
        return cmp.Resistor(f"{r1}k"), cmp.Resistor(f"{r2}k")

    def validate(self):
        if self._output_voltage is not None:
            assert 1 <= self._output_voltage <= 4.5, "Vout test failed"

    @classmethod
    def reference_design(cls, output_voltage, schematic_name="AP7330_Reference"):
        design = schematic.Design(schematic_name)
        ldo = cls()
        design.add_decoupling_cap(ldo.pins.by_name("VIN"), cmp.Capacitor("1u", 10))
        design.add_decoupling_cap(ldo.pins.by_name("VOUT"), cmp.Capacitor("1u", 10))
        r1, r2 = ldo.get_adj_resistors(output_voltage)
        design.connect(ldo.pins.by_name("VOUT"), r1.pins.by_name(1))
        design.connect(ldo.pins.by_name("ADJ"), r1.pins.by_name(2))
        design.connect(ldo.pins.by_name("ADJ"), r2.pins.by_name(1))
        design.connect(ldo.pins.by_name("GND"), r2.pins.by_name(2))
        return design
