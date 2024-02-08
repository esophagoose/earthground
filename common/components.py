import dataclasses

import common.standard_values as sv


@dataclasses.dataclass
class Pin:
    name: str
    index: str
    parent: "Component"

    def __str__(self):
        return f"{self.parent}.{self.index} ({self.name})"

    def __hash__(self):
        return hash((self.name, self.parent))

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
        self.pins = []
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
    def __init__(self, value):
        super().__init__()
        self.value = sv.SiNumber(value, "Ω")
        self.name = f"RES_{self.value}"
        self.description = self.name
        self.pins = PinContainer.from_count(2, self)
        self.refdes_prefix = "R"


class Capacitor(Component):
    def __init__(self, value, voltage):
        super().__init__()
        self.value = sv.SiNumber(value, "F")
        self.voltage = sv.SiNumber(voltage, "V")
        self.name = f"CAP_{self.value}_{self.voltage}"
        self.description = self.name
        self.pins = PinContainer.from_count(2, self)
        self.refdes_prefix = "C"


PASSIVE_TYPES = (Resistor, Capacitor)


class PinContainer:
    def __init__(self, pins):
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

    def by_name(self, name):
        if name in self.names:
            return self.names[name]
        raise ValueError(f"Unknown name: {name} in {self.names}")

    def by_index(self, index):
        if index in self.indicies:
            return self.indicies[index]
        raise ValueError(f"Unknown index: {index} in {self.indicies}")