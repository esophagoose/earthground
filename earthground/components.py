from typing import TYPE_CHECKING, Dict, List, Optional, Set, Union

import earthground.footprint_types as ft
import earthground.standard_values as sv
from earthground.library.footprints import passives

if TYPE_CHECKING:
    import earthground.schematic as sch


class Net:
    def __init__(self, name="UNASSIGNED") -> None:
        """
         Net represents an electrical connection between pins in a circuit

        :param name: The name of the net. Defaults to "UNASSIGNED".
        :type name: str, optional
        """

        self.name = name
        self.connections: Set["Pin"] = set()

    def __repr__(self) -> str:
        return f"Net<{self.name}>"

    def __str__(self) -> str:
        return f"Net<{self.name}>"


class Pin:
    def __init__(self, name: str, index: str, parent: "Component"):
        """
        Initializes a new Pin for a component

        :param name: The name of the pin.
        :type name: str
        :param index: The index of the pin within the component.
        :type index: str
        :param parent: The component this pin is part of.
        :type parent: Component
        """

        self.name = name
        self.index = index
        self.parent = parent

    def __str__(self):
        return f"{self.parent}.{self.index} ({self.name})"

    def __repr__(self):
        return f"{self.parent}.{self.index} ({self.name})"

    def __hash__(self):
        return hash((self.name, self.index, self.parent))

    def __eq__(self, other):
        if not isinstance(other, Pin):
            return False
        return self.name == other.name and (hash(self.parent) == hash(other.parent))

    def add_decoupling_capacitor(
        self, capacitor: "Capacitor", net_name=None, ground_net_name="GND"
    ):
        """
        Helper function to automatically add a decoupling capacitor to a pin

        :param capacitor: The decoupling capacitor to add.
        :param net_name: (Optional) The name of the net to which the capacitor will be connected. If not provided, it will be determined based on the pin.
        :type capacitor: earthground.components.Capacitor
        :type net_name: Optional[str]
        :return: None
        """
        assert isinstance(
            self.parent, Component
        ), "Component must be in a design before adding decoupling capacitor!"
        design: sch.Design = self.parent.parent
        net_name = net_name or design._get_net_name_from_pin(self)
        design.add_component(capacitor)
        design.join_net(self, net_name)
        design.join_net(capacitor.pins[1], net_name)
        design.join_net(capacitor.pins[2], ground_net_name)


class Component:
    REFDES_MAP = {}

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
        self.parent: Optional["Component"] = None
        self.footprint: ft.BaseFootprint = None
        self.virtual = False
        self.dnp = False  # DNP = Do Not Populate
        self.ltspice_model = None
        self._placed = False
        if self.refdes_prefix not in Component.REFDES_MAP:
            Component.REFDES_MAP[self.refdes_prefix] = 0
        Component.REFDES_MAP[self.refdes_prefix] += 1
        self.refdes_index = Component.REFDES_MAP[self.refdes_prefix]

    def __str__(self):
        return f"{self.name}<{self.refdes}>"

    def __repr__(self):
        return f"{self.name}<{self.refdes}|{hash(self)}>"

    def __hash__(self) -> int:
        # TODO: fix hashing to not rely on refdes
        return hash(self.refdes)

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
        if type(self) in [Resistor, Capacitor]:
            package = type(self).__name__[0] + parent.default_passive_size
            self.footprint = passives.PassiveSmd(passives.PassivePackage[package])

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
            for pin_name, net_name in nets.items():
                if net_name is None:
                    continue
                if isinstance(net_name, Pin):
                    self.parent.connect([self.pins.by_name(pin_name), net_name])
                else:
                    self.parent.join_net(self.pins.by_name(pin_name), net_name)
            return self
        elif isinstance(nets, list):
            for i, net_name in enumerate(nets):
                if net_name is None:
                    continue
                self.parent.join_net(self.pins.by_index(i + 1), net_name)
            return self
        raise ValueError("Invalid type for nets")

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


class Resistor(Component):
    def __init__(self, value, **parameters):
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
        self.pins = PinContainer.from_count(2, self)
        self.refdes_prefix = "R"
        self.parameters = parameters


class Capacitor(Component):
    def __init__(self, value, voltage, **parameters):
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
        self.pins = PinContainer.from_count(2, self)
        self.refdes_prefix = "C"
        self.parameters = parameters


PASSIVE_TYPES = (Resistor, Capacitor)


class PinContainer:
    def __init__(self, pins: List[Pin] = []):
        """
        Container for managing a set of pins.

        :param pins: A list of :class:`Pin` objects to be managed.
        :type pins: List[:class:`Pin`]
        """
        self._pins = frozenset(pins)  # TODO: make this ordered
        self.names = {p.name: p for p in pins}
        self.indicies = {p.index: p for p in pins}

    @classmethod
    def from_dict(cls, pin_dict, parent):
        """
        Creates a PinContainer from a dictionary mapping pin names to pin indices.

        :param pin_dict: A dictionary where keys are pin names and values are their corresponding indices.
        :type pin_dict: dict
        :param parent: The parent component to which the pins belong.
        :type parent: Component
        :return: An instance of :class:`PinContainer` populated with :class:`Pin` objects based on the provided dictionary.
        :rtype: PinContainer
        """
        return cls([Pin(n, i, parent) for i, n in pin_dict.items()])

    @classmethod
    def from_list(cls, pin_list, parent):
        """
        Creates a PinContainer from a list of pin names, assigning indices sequentially

        :param pin_list: A list of pin names for which :class:`Pin` objects will be created.
        :type pin_list: List[str]
        :param parent: The parent component to which the pins belong.
        :type parent: Component
        :return: An instance of :class:`PinContainer` populated with :class:`Pin` objects.
        :rtype: PinContainer
        """
        return cls([Pin(n, i, parent) for i, n in enumerate(pin_list)])

    @classmethod
    def from_count(cls, pin_count: int, parent: Component):
        """
        Creates a PinContainer with a specified number of pins, numbered sequentially.

        :param pin_count: The number of pins to create.
        :type pin_count: int
        :param parent: The parent component to which the pins belong.
        :type parent: Component
        :return: An instance of :class:`PinContainer` populated with sequentially numbered :class:`Pin` objects.
        :rtype: PinContainer
        """
        return cls([Pin(str(i), i, parent) for i in range(1, pin_count + 1)])

    def __getitem__(self, index):
        return self.by_index(index)

    def __iter__(self) -> Pin:
        return iter(self._pins)

    def __len__(self):
        return len(self._pins)

    def by_name(self, name):
        """
        Returns the pin with the specified name.

        :param name: The name of the pin to retrieve.
        :type name: str
        :raises ValueError: If the pin name does not exist.
        :return: The :class:`Pin` object with the specified name.
        :rtype: Pin
        """
        if name in self.names:
            return self.names[name]
        raise ValueError(f"Unknown name: {name} in {self.names.keys()}")

    def by_index(self, index):
        """
        Returns the pin with the specified index.

        :param index: The index of the pin to retrieve.
        :type index: int
        :raises ValueError: If the pin index does not exist.
        :return: The :class:`Pin` object with the specified index.
        :rtype: Pin
        """
        if index in self.indicies:
            return self.indicies[index]
        raise ValueError(f"Unknown index: {index} in {self.indicies}")

    def all_with_name(self, name: Union[str, List[str]]):
        """
        Yields all pins with the specified name or names.

        :param name: The name or names of the pins to yield.
        :type name: Union[str, List[str]]
        :raises ValueError: If the name parameter is not a string or a list of strings.
        """
        if not isinstance(name, (str, list)):
            raise ValueError("'name' must be a str or list of str!")
        for pin in self._pins:
            if isinstance(name, str) and pin.name == name:
                yield pin
            elif isinstance(name, list) and pin.name in name:
                yield pin


def pin_sort_key(pin: "Pin") -> tuple:
    """
    Sort key function for pins with the following priority:
    1. Numeric pins (sorted numerically) - come first
    2. Regular alphabetical pins
    3. GND and SHIELD - come last

    :param pin: The pin to generate a sort key for
    :type pin: Pin
    :return: Tuple for sorting (priority, value)
    :rtype: tuple
    """
    name = pin.name
    # Check if the name can be converted to a number
    try:
        numeric_value = int(name)
        # Numeric pins get priority 0 (first)
        return (0, numeric_value)
    except ValueError:
        # Not a number, check if it's GND or SHIELD
        if name.upper() in ("GND", "SHIELD"):
            # GND and SHIELD get priority 2 (last)
            return (2, name.upper())
        else:
            # Regular pins get priority 1 (middle), sorted alphabetically
            return (1, name.upper())
