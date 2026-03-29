import earthground.components as cmp
import earthground.schematic as sch

DEFAULT_PORTS = ["VLOGIC", "GND", "IN+", "IN-", "OUT"]


class CurrentSenseAmplifier(cmp.Component):
    """
    Base class for current sense amplifiers.
    """

    def __init__(self, gain: float, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gain = gain


class CurrentSenseDesign(sch.Design):
    """
    Extension of sch.Design for current sense amplifiers with common analysis methods.
    """

    def __init__(
        self,
        name: str,
        current_sense_amplifier: CurrentSenseAmplifier,
        sense_resistor: cmp.Resistor,
    ):
        """
        gain_v_v: The voltage gain (V/V) of the current sense amplifier
        sense_resistor_ohms: The resistance of the shunt/sense resistor (Ω)
        """
        super().__init__(name, short_name="CSA", ports=DEFAULT_PORTS)
        if not current_sense_amplifier.gain:
            raise ValueError("Current sense amplifier must have a gain.")
        self.csa: CurrentSenseAmplifier = self.add_component(current_sense_amplifier)
        self.sense_resistor: cmp.Resistor = self.add_component(sense_resistor)
        for port in DEFAULT_PORTS:
            self.connect([self.csa.pins.by_name(port), self.port[port]], port)
        self.connect([self.sense_resistor.pins[1], self.port["IN+"]], "IN+")
        self.connect([self.sense_resistor.pins[2], self.port["IN-"]], "IN-")

    def get_vout_from_current(self, i_shunt: float) -> float:
        """
        Compute output voltage for a given sense current (in Amperes)
        """
        return i_shunt * self.sense_resistor.value.value * self.csa.gain

    def get_power_through_sense_resistor(self, i_shunt):
        """
        Compute power dissipated in the sense resistor (in Watts) for a given current (in Amperes)
        """
        return (i_shunt**2) * self.sense_resistor.value.value
