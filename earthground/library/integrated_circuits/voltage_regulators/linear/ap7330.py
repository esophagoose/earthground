import earthground.components as cmp
import earthground.contracts as contracts
import earthground.schematic as schematic
import earthground.standard_values as sv
import earthground.thermal as thermal
from earthground.library._intent import typed_pin_map
from earthground.ratings import Ratings


class AP7330(cmp.Component):
    SOURCE = "AP7330 datasheet DS40022 Rev. 2-2"
    abs_max = Ratings(
        vin=sv.volts(min=sv.UNBOUNDED, max=6, source=SOURCE),
        i_out=sv.amps(min=sv.UNBOUNDED, max=0.3, source=SOURCE),
        tstg=sv.celsius(-55, max=125, source=SOURCE),
    )
    recommended = Ratings(
        vin=sv.volts(1.8, max=5.5, source=SOURCE),
        vout=sv.volts(1, max=4.5, source=SOURCE),
        i_out=sv.amps(0, max=0.3, source=SOURCE),
        ta=sv.celsius(-40, max=85, source=SOURCE),
    )

    def __init__(self):
        super().__init__()
        self.name = "AP7330"
        self.mpn = "AP7330"
        self.manufacturer = "Diodes Incorporated"
        self.description = "Adjustable low-dropout linear regulator"
        self.datasheet = "https://www.diodes.com/datasheet/download/AP7330.pdf"
        self.datasheet_revision = "DS40022 Rev. 2-2"
        self.lifecycle = cmp.Lifecycle.UNKNOWN
        self.pins = cmp.PinContainer.from_dict(
            typed_pin_map(
                {1: "VIN", 2: "GND", 3: "EN", 4: "ADJ", 5: "VOUT"},
                digital_inputs={"EN"},
                analog_inputs={"ADJ"},
                power_inputs={"VIN": None},
                power_outputs={"VOUT": self.recommended["vout"]},
                grounds={"GND"},
                source=self.SOURCE,
            ),
            self,
        )
        self.requires = (
            contracts.Decoupling(
                id="vin-decoupling",
                pin="VIN",
                capacitance=sv.farads(min="1u", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
            contracts.Decoupling(
                id="vout-decoupling",
                pin="VOUT",
                capacitance=sv.farads(min="1u", max=sv.UNBOUNDED),
                source=self.SOURCE,
            ),
        )
        self.thermal = thermal.ThermalModel(
            r_ja=sv.celsius_per_watt(typ=179, source=self.SOURCE),
            r_jc_top=sv.celsius_per_watt(typ=52, source=self.SOURCE),
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
        ldo = design.add_component(cls())
        ldo.pins.by_name("VIN").add_decoupling_capacitor(cmp.Capacitor("1u", 10))
        ldo.pins.by_name("VOUT").add_decoupling_capacitor(cmp.Capacitor("1u", 10))
        r1, r2 = ldo.get_adj_resistors(output_voltage)
        design.add_component(r1)
        design.add_component(r2)
        design.connect([ldo.pins.by_name("VOUT"), r1.pins[1]])
        design.connect([ldo.pins.by_name("ADJ"), r1.pins[2]])
        design.connect([ldo.pins.by_name("ADJ"), r2.pins[1]])
        design.connect([ldo.pins.by_name("GND"), r2.pins[2]])
        return design
