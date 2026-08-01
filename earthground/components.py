from typing import TYPE_CHECKING, Dict, List, Optional, Set

import earthground.footprint_types as ft
from earthground.pins import (
    AnalogPinRatings,
    AnalogPinSpec,
    BasePinRatings,
    BasePinSpec,
    ConnectionPolicy,
    DifferentialInterfaceSpec,
    DifferentialPolarity,
    DigitalMode,
    DigitalPinRatings,
    DigitalPinSpec,
    DriveStyle,
    ErcCharacteristics,
    InternalDigitalFeatures,
    NoConnectPinSpec,
    PassivePinSpec,
    Pin,
    PinContainer,
    PinDirection,
    PinInterfaceRef,
    PinSpec,
    PowerPinSpec,
    PowerRole,
    RelativeThreshold,
    SignalDomain,
    UnspecifiedPinSpec,
    UnusedPolicy,
    pin_sort_key,
)
from earthground.ratings import Ratings
import earthground.standard_values as sv

if TYPE_CHECKING:
    import earthground.schematic as sch


def validate_net_name(
    value: object,
    *,
    owner: str,
    argument: str = "net_name",
) -> str:
    """Return a valid net name or raise before it can enter design state."""
    if not isinstance(value, str):
        raise TypeError(
            f"{owner} argument '{argument}' must be a str, "
            f"got {type(value).__name__}"
        )
    if not value:
        raise ValueError(f"{owner} argument '{argument}' cannot be empty")
    return value


def validate_net_names(owner: str, **names: object) -> None:
    for argument, value in names.items():
        validate_net_name(value, owner=owner, argument=argument)


class Net:
    def __init__(self, name: str = "UNASSIGNED") -> None:
        """
         Net represents an electrical connection between pins in a circuit

        :param name: The name of the net. Defaults to "UNASSIGNED".
        :type name: str, optional
        """

        self._name = ""
        self.name = name
        self.connections: Set["Pin"] = set()

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = validate_net_name(value, owner="Net()", argument="name")

    def __repr__(self) -> str:
        return f"Net<{self.name}>"

    def __str__(self) -> str:
        return f"Net<{self.name}>"


class Component:
    REFDES_MAP = {}
    abs_max = Ratings()
    recommended = Ratings()
    strap_pins = ()
    requires = ()
    thermal = None
    power = None

    def __init__(self, refdes_prefix="U"):
        """
        Component base class with an optional reference designator prefix.

        :param refdes_prefix: The prefix for the refdes, defaults to "U".
        :type refdes_prefix: str, optional
        """

        self.refdes_index = None
        self.refdes_prefix = refdes_prefix
        self.refdes_postfix = ""
        self.name = ""
        self.mpn = ""
        self.type = self.__class__.__name__
        self.parameters = {}
        self.pins = PinContainer()
        self.interfaces: Dict[str, DifferentialInterfaceSpec] = {}
        self.parent: Optional["Component"] = None
        self.footprint: ft.BaseFootprint = None
        self.virtual = False
        self.dnp = False  # DNP = Do Not Populate
        self.ltspice_model = None
        self.strap_pins = tuple(type(self).strap_pins)
        self.requires = tuple(type(self).requires)
        self.thermal = type(self).thermal
        self.power = type(self).power
        self._placed = False
        if self.refdes_prefix not in Component.REFDES_MAP:
            Component.REFDES_MAP[self.refdes_prefix] = 0
        Component.REFDES_MAP[self.refdes_prefix] += 1
        self.refdes_index = Component.REFDES_MAP[self.refdes_prefix]

    def __str__(self):
        return f"{self.name}<{self.refdes}>"

    def __repr__(self):
        return f"{self.name}<{self.refdes}>"

    @property
    def refdes(self):
        """
        Generates the full reference designator for the component.

        :return: The full reference designator as a string.
        :rtype: str
        """

        postfix = self.refdes_postfix
        if postfix and not postfix.startswith("_"):
            postfix = "_" + postfix
        return f"{self.refdes_prefix}{self.refdes_index}{postfix}"

    @property
    def is_in_design(self):
        return self._placed

    def place(self, parent: "sch.Design"):
        self.parent = parent
        self._placed = True

    def set_pins(self, nets: List[str] | Dict[str, str | Pin]) -> "Component":
        """
        Sets the pins for the component based on a list of net names or a dictionary mapping pin names to net names.

        :param nets: A list of net names or a dictionary mapping pin names to net names.
        :type nets: List[str] or Dict[str, str | Pin]
        :return: The component with the pins set.
        :rtype: Component
        """
        if not self._placed:
            raise ValueError("Component must be placed before setting pin nets!")
        if isinstance(nets, dict):
            items = ((self.pins.by_name(name), value) for name, value in nets.items())
        elif isinstance(nets, list):
            items = (
                (self.pins.by_index(index), value)
                for index, value in enumerate(nets, start=1)
            )
        else:
            raise ValueError("Invalid type for nets")

        connections = [(pin, value) for pin, value in items if value is not None]
        validate_net_names(
            "set_pins()",
            **{
                f"net_name_{index}": value
                for index, (_, value) in enumerate(connections)
                if not isinstance(value, Pin)
            },
        )
        for pin, connection in connections:
            if isinstance(connection, Pin):
                self.parent.connect([pin, connection])
            else:
                self.parent.join_net(pin, connection)
        return self

    def print(self):
        pad = max([len(p.name) for p in self.pins]) + 2
        print(f"{self.refdes} ({self.name})")
        print("." + "-" * pad + ".")
        for pin in sorted(self.pins, key=pin_sort_key):
            connection = "<NO CONNECTION>"
            if pin in self.parent.pin_to_net:
                connection = self.parent.pin_to_net[pin].name
            print(f"|{pin.name.rjust(pad)}|-- {connection}")
        print("'" + "-" * pad + "'\n")


class ModuleComponent(Component):
    def __init__(self, refdes_prefix="U"):
        super().__init__(refdes_prefix)


class Resistor(Component):
    def __init__(self, value, **kwargs):
        """
        Resistor with a specified value and optional parameters.

        :param value: The resistance value of the resistor.
        :type value: str or :class:`sv.SiNumber`
        :param parameters: Additional parameters for the resistor.
        :type parameters: dict, optional
        """
        super().__init__()
        self.value = value
        if not isinstance(value, sv.SiNumber):
            self.value = sv.SiNumber(value, "Ω")
        self.name = f"RES_{self.value}"
        self.description = self.name
        self.pins = PinContainer.from_count(2, self, spec_class=PassivePinSpec)
        self.refdes_prefix = "R"
        self.parameters = {}
        self.package_size = None
        for key, value in kwargs.items():
            setattr(self, key, value)


class Capacitor(Component):
    def __init__(self, value, voltage, **kwargs):
        """
        Capacitor with a specified value, voltage, and optional parameters.

        :param value: The capacitance value of the capacitor.
        :type value: str or :class:`sv.SiNumber`
        :param voltage: The voltage rating of the capacitor.
        :type voltage: str or :class:`sv.SiNumber`
        :param parameters: Additional parameters for the capacitor.
        :type parameters: dict, optional
        """
        super().__init__()
        self.value = sv.SiNumber(value, "F")
        self.voltage = sv.SiNumber(voltage, "V")
        self.name = f"CAP_{self.value}_{self.voltage}"
        self.description = self.name
        self.pins = PinContainer.from_count(2, self, spec_class=PassivePinSpec)
        self.refdes_prefix = "C"
        self.package_size = None
        for key, val in kwargs.items():
            setattr(self, key, val)


class Inductor(Component):
    def __init__(self, value, **kwargs):
        """
        Inductor with a specified value and optional parameters.

        :param value: The inductance value of the inductor.
        :type value: str or :class:`sv.SiNumber`
        :param kwargs: Additional parameters (e.g. current, dcr, package_size).
        :type kwargs: dict, optional
        """
        super().__init__(refdes_prefix="L")
        if not isinstance(value, sv.SiNumber):
            self.value = sv.SiNumber(value, "H")
        else:
            self.value = value
        self.name = f"IND_{self.value}"
        self.description = self.name
        self.pins = PinContainer.from_count(2, self, spec_class=PassivePinSpec)
        self.package_size = None
        for key, val in kwargs.items():
            setattr(self, key, val)


PASSIVE_TYPES = (Resistor, Capacitor, Inductor)
