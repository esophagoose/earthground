from typing import List, Union

import common.standard_values as sv


class Net:
    def __init__(self, name="UNASSIGNED") -> None:
        self.name = name
        self.connections = set()

    def __repr__(self) -> str:
        return f"Net<{self.name}>"

    def __str__(self) -> str:
        return f"Net<{self.name}>"

    def add(self, pin: "Pin"):
        self.connections.add(pin)

    def extend(self, pins: List["Pin"]):
        for pin in pins:
            self.connections.add(pin)


class Pin:
    def __init__(self, name: str, index: str, parent: "Component"):
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


class Component:
    REFDES_MAP = {}

    def __init__(self, refdes_prefix="U"):
        self.refdes_index = None
        self.refdes_prefix = refdes_prefix
        self.refdes_postfix = ""
        self.name = ""
        self.mpn = ""
        self.type = self.__class__.__name__
        self.parameters = {}
        self.pins = PinContainer([])
        self.parent = None
        self.footprint = None
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
        postfix = self.refdes_postfix
        if postfix and not postfix.startswith("_"):
            postfix = "_" + postfix
        return f"{self.refdes_prefix}{self.refdes_index}{postfix}"


class Resistor(Component):
    def __init__(self, value, **parameters):
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
    def __init__(self, pins: List[Pin]):
        self._pins = frozenset(pins)
        self.names = {p.name: p for p in pins}
        self.indicies = {p.index: p for p in pins}

    @classmethod
    def from_dict(cls, pin_dict, parent):
        return cls([Pin(n, i, parent) for i, n in pin_dict.items()])

    @classmethod
    def from_list(cls, pin_list, parent):
        return cls([Pin(n, i, parent) for i, n in enumerate(pin_list)])

    @classmethod
    def from_count(cls, pin_count: int, parent: Component):
        return cls([Pin(str(i), i, parent) for i in range(1, pin_count + 1)])

    def __getitem__(self, index):
        return self.by_index(index)

    def __iter__(self) -> Pin:
        return iter(self._pins)

    def __len__(self):
        return len(self._pins)

    def by_name(self, name):
        if name in self.names:
            return self.names[name]
        raise ValueError(f"Unknown name: {name} in {self.names}")

    def by_index(self, index):
        if index in self.indicies:
            return self.indicies[index]
        raise ValueError(f"Unknown index: {index} in {self.indicies}")

    def all_with_name(self, name: Union[str, List[str]]):
        if not isinstance(name, (str, list)):
            raise ValueError("'name' must be a str or list of str!")
        for pin in self._pins:
            if isinstance(name, str) and pin.name == name:
                yield pin
            elif isinstance(name, list) and pin.name in name:
                yield pin
