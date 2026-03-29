import enum
from typing import List, NamedTuple

import earthground.components as cmp
import earthground.layout as layout
import earthground.schematic as sch_lib
import earthground.standard_values as sv


class SingleInterfaceOpAmp(NamedTuple):
    in_n: cmp.Pin
    in_p: cmp.Pin
    out: cmp.Pin


class OpAmpConfigurations(enum.Enum):
    NONINVERTING = "generate_noninverting_amplifier"


class OpAmpBase(cmp.Component):
    def __init__(self, base_channel_name: str, channel_count: int):
        super().__init__()
        self.base_channel_name = base_channel_name
        self.channel_count = channel_count

    def get_interface(self, index: int = 1) -> SingleInterfaceOpAmp:
        """
        Get the interface for a specific op-amp channel.

        Args:
            index: Index number (1, 2, 3, or 4)

        Returns:
            SingleInterfaceOpAmp with in_n, in_p, and out pins
        """
        if index < 1 or index > self.channel_count:
            raise ValueError(f"Invalid index: {index}. Must be 1 - 4")
        channel = chr(ord(self.base_channel_name) + index - 1)
        return SingleInterfaceOpAmp(
            in_n=self.pins.by_name(f"IN{channel}-"),
            in_p=self.pins.by_name(f"IN{channel}+"),
            out=self.pins.by_name(f"OUT{channel}"),
        )

    def generate_design(self, channel_config: List[OpAmpConfigurations], gain: float):
        if len(channel_config) != self.channel_count:
            raise ValueError(
                f"Op-amp only supports {self.channel_count} channels. Received {len(channel_config)}"
            )
        ports = ["V+", "V-"] + [f"IN_{i+1}" for i in range(self.channel_count)]
        ports += [f"OUT_{i+1}" for i in range(self.channel_count)]
        design = sch_lib.Design(self.name, "OPAMP", ports)
        opamp = design.add_component(self)
        cap = design.add_component(cmp.Capacitor("1u", 16))
        design.connect([cap.pins[1], opamp.pins.by_name("V+"), design.port["V+"]], "V+")
        design.connect([cap.pins[2], opamp.pins.by_name("V-"), design.port["V-"]], "V-")
        for i in range(self.channel_count):
            if channel_config[i].value == OpAmpConfigurations.NONINVERTING.value:
                self._generate_noninverting_amplifier(design, gain, i + 1)
                interface = self.get_interface(i + 1)
                design.connect([interface.out, design.port[f"OUT_{i+1}"]], f"OUT_{i+1}")
                design.connect([interface.in_p, design.port[f"IN_{i+1}"]], f"IN_{i+1}")
            else:
                raise NotImplementedError(
                    f"Unsupported op-amp configuration: {channel_config[i]}"
                )
        design.layout.outline = layout.BoundingBox(x1=-15.0, y1=-8, x2=15.0, y2=8)
        design.layout.placement = {
            "C1": layout.Placement(
                id=layout.Orientation.LEFT,
                position=layout.Position(x=-6.0, y=0.0, angle=180),
            ),
            "R1": layout.Placement(
                id=layout.Orientation.LEFT,
                position=layout.Position(x=-6.0, y=-1.5, angle=180.0),
            ),
            "R2": layout.Placement(
                id=layout.Orientation.TOP,
                position=layout.Position(x=4.0, y=-3.5, angle=180.0),
            ),
            "R3": layout.Placement(
                id=layout.Orientation.TOP,
                position=layout.Position(x=-4.0, y=-3.5, angle=0.0),
            ),
            "R4": layout.Placement(
                id=layout.Orientation.TOP,
                position=layout.Position(x=-6.0, y=1.5, angle=180.0),
            ),
            "R5": layout.Placement(
                id=layout.Orientation.TOP,
                position=layout.Position(x=4.0, y=3.5, angle=180.0),
            ),
            "R6": layout.Placement(
                id=layout.Orientation.TOP,
                position=layout.Position(x=6.0, y=1.5, angle=0.0),
            ),
            "R7": layout.Placement(
                id=layout.Orientation.TOP,
                position=layout.Position(x=-4.0, y=3.5, angle=180.0),
            ),
            "R8": layout.Placement(
                id=layout.Orientation.TOP,
                position=layout.Position(x=6.0, y=-1.5, angle=0.0),
            ),
            "U1": layout.Placement(
                id=layout.Orientation.BOTTOM,
                position=layout.Position(x=0.0, y=0.0, angle=0.0),
            ),
        }
        return design

    def _generate_noninverting_amplifier(
        self, design: sch_lib.Design, gain: float, index: int = 1
    ):
        """
        Generate a noninverting amplifier using an op-amp and return the output pin.

        Args:
            design: The design to add components to
            opamp: The op-amp component (already added to design)
            gain: The gain for the amplifier (must be >= 1)
            input_net: The input net name
            index: The op-amp channel index (1-4)

        Returns:
            The output pin of the amplifier
        """

        if gain < 1:
            raise ValueError(
                f"Gain must be >= 1 for noninverting amplifier, got {gain}"
            )

        interface = self.get_interface(index)

        # Noninverting amplifier: Vout = Vin * (1 + R2/R1)
        # So R2/R1 = gain - 1
        # Use standard resistor values
        ratio = gain - 1
        r2_value, r1_value = sv.find_closest_ratio(ratio)

        r1 = design.add_component(cmp.Resistor(f"{r1_value}k", tolerance="0.1%"))
        r2 = design.add_component(cmp.Resistor(f"{r2_value}k", tolerance="0.1%"))

        # Connect input to non-inverting input
        letter = chr(ord(self.base_channel_name) + index - 1)
        design.connect([interface.in_p, design.port[f"IN_{index}"]], f"IN_{letter}_P")

        # Connect R1 between inverting input and ground
        design.connect([interface.in_n, r1.pins[1]], f"IN_{letter}_N")
        design.join_net(r1.pins[2], "V-")

        # Connect R2 between inverting input and output (feedback)
        design.connect([interface.in_n, r2.pins[1]], f"IN_{letter}_N")
        design.connect([interface.out, r2.pins[2]], f"OUT_{letter}")

        return interface.out
