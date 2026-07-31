import enum
from dataclasses import dataclass, field
from decimal import Decimal
from typing import ClassVar, List, Optional, Union

import earthground.standard_values as sv


class SignalDomain(enum.Enum):
    DIGITAL = enum.auto()
    ANALOG = enum.auto()
    POWER = enum.auto()
    PASSIVE = enum.auto()
    UNSPECIFIED = enum.auto()


class PinDirection(enum.Enum):
    INPUT = enum.auto()
    OUTPUT = enum.auto()
    BIDIRECTIONAL = enum.auto()
    PASSIVE = enum.auto()


class DriveStyle(enum.Enum):
    PUSH_PULL = enum.auto()
    OPEN_DRAIN = enum.auto()
    TRI_STATE = enum.auto()
    UNSPECIFIED = enum.auto()


class ConnectionPolicy(enum.Enum):
    REQUIRED = enum.auto()
    OPTIONAL = enum.auto()
    MUST_NOT_CONNECT = enum.auto()


class PowerRole(enum.Enum):
    INPUT = enum.auto()
    OUTPUT = enum.auto()
    GROUND = enum.auto()


class DifferentialPolarity(enum.Enum):
    POSITIVE = enum.auto()
    NEGATIVE = enum.auto()


class UnusedPolicy(enum.Enum):
    UNSPECIFIED = enum.auto()
    LEAVE_UNCONNECTED = enum.auto()


@dataclass(frozen=True)
class RelativeThreshold:
    factor: Decimal
    ref: str

    def __init__(self, factor, ref: str):
        if not ref:
            raise ValueError("Relative threshold requires a reference")
        object.__setattr__(self, "factor", Decimal(str(factor)))
        object.__setattr__(self, "ref", ref)


Threshold = Union[sv.ValueBounds, RelativeThreshold]


@dataclass(frozen=True)
class BasePinRatings:
    voltage_abs_max: Optional[sv.ValueBounds] = None
    voltage_operating: Optional[sv.ValueBounds] = None
    current_max: Optional[sv.ValueBounds] = None

    def __post_init__(self):
        sv.require_bounds(self.voltage_abs_max, "V", "voltage_abs_max", allow_none=True)
        sv.require_bounds(
            self.voltage_operating, "V", "voltage_operating", allow_none=True
        )
        sv.require_bounds(self.current_max, "A", "current_max", allow_none=True)


@dataclass(frozen=True)
class DigitalPinRatings(BasePinRatings):
    threshold_high: Optional[Threshold] = None
    threshold_low: Optional[Threshold] = None

    def __post_init__(self):
        super().__post_init__()
        for label, threshold in (
            ("threshold_high", self.threshold_high),
            ("threshold_low", self.threshold_low),
        ):
            if isinstance(threshold, sv.ValueBounds):
                sv.require_bounds(threshold, "V", label)
            elif threshold is not None and not isinstance(threshold, RelativeThreshold):
                raise TypeError(f"{label} must be ValueBounds or RelativeThreshold")


@dataclass(frozen=True)
class AnalogPinRatings(BasePinRatings):
    pass


@dataclass(frozen=True)
class DigitalMode:
    name: str
    direction: PinDirection
    drive_style: DriveStyle = DriveStyle.UNSPECIFIED
    voltage_operating: Optional[sv.ValueBounds] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Digital mode requires a name")
        if not isinstance(self.direction, PinDirection):
            raise TypeError("direction must be PinDirection")
        if not isinstance(self.drive_style, DriveStyle):
            raise TypeError("drive_style must be DriveStyle")
        if self.direction is PinDirection.PASSIVE:
            raise ValueError("Digital modes cannot use PASSIVE direction")
        sv.require_bounds(
            self.voltage_operating, "V", "voltage_operating", allow_none=True
        )


@dataclass(frozen=True)
class InternalDigitalFeatures:
    pull_up: Optional[bool] = None
    pull_down: Optional[bool] = None
    termination: Optional[str] = None

    def __post_init__(self):
        for label, value in (("pull_up", self.pull_up), ("pull_down", self.pull_down)):
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{label} must be bool or None")


@dataclass(frozen=True)
class PinInterfaceRef:
    interface: str
    polarity: Optional[DifferentialPolarity] = None

    def __post_init__(self):
        if not self.interface:
            raise ValueError("Pin interface reference requires an interface name")
        if self.polarity is not None and not isinstance(
            self.polarity, DifferentialPolarity
        ):
            raise TypeError("polarity must be DifferentialPolarity")


@dataclass(frozen=True)
class ErcCharacteristics:
    directions: frozenset[PinDirection]
    drive_styles: frozenset[DriveStyle]
    connection: ConnectionPolicy
    voltage_operating: Optional[sv.ValueBounds] = None
    voltage_abs_max: Optional[sv.ValueBounds] = None
    current_max: Optional[sv.ValueBounds] = None
    power_role: Optional[PowerRole] = None


@dataclass(frozen=True, kw_only=True)
class BasePinSpec:
    name: str
    description: Optional[str] = None
    connection: ConnectionPolicy = ConnectionPolicy.OPTIONAL
    source: Optional[str] = None

    domain: ClassVar[SignalDomain] = SignalDomain.UNSPECIFIED

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Pin specification requires a non-empty string name")
        if not isinstance(self.connection, ConnectionPolicy):
            raise TypeError("connection must be ConnectionPolicy")

    def erc_characteristics(self) -> ErcCharacteristics:
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class DigitalPinSpec(BasePinSpec):
    modes: tuple[DigitalMode, ...]
    ratings: DigitalPinRatings = field(default_factory=DigitalPinRatings)
    internal: InternalDigitalFeatures = field(default_factory=InternalDigitalFeatures)
    interface: Optional[PinInterfaceRef] = None

    domain: ClassVar[SignalDomain] = SignalDomain.DIGITAL

    def __post_init__(self):
        super().__post_init__()
        if not self.modes:
            raise ValueError("DigitalPinSpec requires at least one mode")
        names = [mode.name for mode in self.modes]
        if len(names) != len(set(names)):
            raise ValueError("Digital mode names must be unique")

    def erc_characteristics(self) -> ErcCharacteristics:
        mode_operating = {
            mode.voltage_operating
            for mode in self.modes
            if mode.voltage_operating is not None
        }
        operating = self.ratings.voltage_operating
        if operating is None and len(mode_operating) == 1:
            operating = next(iter(mode_operating))
        return ErcCharacteristics(
            directions=frozenset(mode.direction for mode in self.modes),
            drive_styles=frozenset(mode.drive_style for mode in self.modes),
            connection=self.connection,
            voltage_operating=operating,
            voltage_abs_max=self.ratings.voltage_abs_max,
            current_max=self.ratings.current_max,
        )

    @classmethod
    def single_mode(
        cls,
        direction: PinDirection,
        *,
        drive_style: DriveStyle = DriveStyle.UNSPECIFIED,
        mode_name: str = "default",
        voltage_abs_max: Optional[sv.ValueBounds] = None,
        voltage_operating: Optional[sv.ValueBounds] = None,
        current_max: Optional[sv.ValueBounds] = None,
        threshold_high: Optional[Threshold] = None,
        threshold_low: Optional[Threshold] = None,
        **kwargs,
    ):
        return cls(
            modes=(
                DigitalMode(
                    mode_name,
                    direction,
                    drive_style=drive_style,
                ),
            ),
            ratings=DigitalPinRatings(
                voltage_abs_max=voltage_abs_max,
                voltage_operating=voltage_operating,
                current_max=current_max,
                threshold_high=threshold_high,
                threshold_low=threshold_low,
            ),
            **kwargs,
        )

    @classmethod
    def input(cls, **kwargs):
        return cls.single_mode(PinDirection.INPUT, **kwargs)

    @classmethod
    def output(cls, **kwargs):
        return cls.single_mode(PinDirection.OUTPUT, **kwargs)

    @classmethod
    def bidirectional(cls, **kwargs):
        return cls.single_mode(PinDirection.BIDIRECTIONAL, **kwargs)


@dataclass(frozen=True, kw_only=True)
class AnalogPinSpec(BasePinSpec):
    direction: PinDirection
    ratings: AnalogPinRatings = field(default_factory=AnalogPinRatings)
    input_impedance: Optional[sv.ValueBounds] = None
    bandwidth: Optional[sv.ValueBounds] = None
    interface: Optional[PinInterfaceRef] = None

    domain: ClassVar[SignalDomain] = SignalDomain.ANALOG

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.direction, PinDirection):
            raise TypeError("direction must be PinDirection")
        if self.direction is PinDirection.PASSIVE:
            raise ValueError("AnalogPinSpec cannot use PASSIVE direction")
        sv.require_bounds(self.input_impedance, "Ω", "input_impedance", allow_none=True)
        sv.require_bounds(self.bandwidth, "Hz", "bandwidth", allow_none=True)

    def erc_characteristics(self) -> ErcCharacteristics:
        return ErcCharacteristics(
            directions=frozenset((self.direction,)),
            drive_styles=frozenset(),
            connection=self.connection,
            voltage_operating=self.ratings.voltage_operating,
            voltage_abs_max=self.ratings.voltage_abs_max,
            current_max=self.ratings.current_max,
        )

    @classmethod
    def input(cls, **kwargs):
        return cls(direction=PinDirection.INPUT, **kwargs)

    @classmethod
    def output(cls, **kwargs):
        return cls(direction=PinDirection.OUTPUT, **kwargs)


@dataclass(frozen=True, kw_only=True)
class PowerPinSpec(BasePinSpec):
    role: PowerRole
    voltage: Optional[sv.ValueBounds] = None
    abs_max: Optional[sv.ValueBounds] = None
    current_max: Optional[sv.ValueBounds] = None

    domain: ClassVar[SignalDomain] = SignalDomain.POWER

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.role, PowerRole):
            raise TypeError("role must be PowerRole")
        sv.require_bounds(self.voltage, "V", "voltage", allow_none=True)
        sv.require_bounds(self.abs_max, "V", "abs_max", allow_none=True)
        sv.require_bounds(self.current_max, "A", "current_max", allow_none=True)

    def erc_characteristics(self) -> ErcCharacteristics:
        direction = (
            PinDirection.OUTPUT if self.role is PowerRole.OUTPUT else PinDirection.INPUT
        )
        return ErcCharacteristics(
            directions=frozenset((direction,)),
            drive_styles=frozenset(),
            connection=self.connection,
            voltage_operating=self.voltage,
            voltage_abs_max=self.abs_max,
            current_max=self.current_max,
            power_role=self.role,
        )


@dataclass(frozen=True, kw_only=True)
class PassivePinSpec(BasePinSpec):
    domain: ClassVar[SignalDomain] = SignalDomain.PASSIVE

    def erc_characteristics(self) -> ErcCharacteristics:
        return ErcCharacteristics(
            directions=frozenset((PinDirection.PASSIVE,)),
            drive_styles=frozenset(),
            connection=self.connection,
        )


@dataclass(frozen=True, kw_only=True)
class NoConnectPinSpec(BasePinSpec):
    connection: ConnectionPolicy = field(
        default=ConnectionPolicy.MUST_NOT_CONNECT, init=False
    )

    def erc_characteristics(self) -> ErcCharacteristics:
        return ErcCharacteristics(
            directions=frozenset(),
            drive_styles=frozenset(),
            connection=self.connection,
        )


@dataclass(frozen=True, kw_only=True)
class UnspecifiedPinSpec(BasePinSpec):
    def erc_characteristics(self) -> ErcCharacteristics:
        return ErcCharacteristics(
            directions=frozenset(),
            drive_styles=frozenset(),
            connection=self.connection,
        )


PinSpec = Union[
    DigitalPinSpec,
    AnalogPinSpec,
    PowerPinSpec,
    PassivePinSpec,
    NoConnectPinSpec,
    UnspecifiedPinSpec,
]


@dataclass(frozen=True, kw_only=True)
class DifferentialInterfaceSpec:
    name: str
    positive: str
    negative: str
    target_impedance: Optional[sv.ValueBounds] = None
    unused_policy: UnusedPolicy = UnusedPolicy.UNSPECIFIED
    required_external: Optional[str] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Differential interface requires a name")
        if self.positive == self.negative:
            raise ValueError("Differential interface pins must be distinct")
        sv.require_bounds(
            self.target_impedance, "Ω", "target_impedance", allow_none=True
        )


class Pin:
    def __init__(
        self,
        name: str,
        index: str,
        parent,
        spec: Optional[BasePinSpec] = None,
    ):
        self.name = name
        self.index = index
        self.parent = parent
        self.spec = spec or UnspecifiedPinSpec(name=name)

    @property
    def spec(self) -> BasePinSpec:
        return self._spec

    @spec.setter
    def spec(self, value: BasePinSpec):
        if not isinstance(value, BasePinSpec):
            raise TypeError("spec must inherit BasePinSpec")
        if value.name != self.name:
            raise ValueError(
                f"Pin name {self.name!r} does not match PinSpec {value.name!r}"
            )
        self._spec = value

    @property
    def erc(self) -> ErcCharacteristics:
        return self.spec.erc_characteristics()

    @property
    def abs_max(self):
        return self.erc.voltage_abs_max

    @property
    def operating(self):
        return self.erc.voltage_operating

    def __str__(self):
        return f"{self.parent}.{self.index} ({self.name})"

    def __repr__(self):
        return f"{self.parent}.{self.index} ({self.name})"

    def __hash__(self):
        return hash((self.name, self.index, id(self.parent)))

    def __eq__(self, other):
        if not isinstance(other, Pin):
            return False
        return (
            self.name == other.name
            and self.index == other.index
            and self.parent is other.parent
        )

    @property
    def net(self):
        return self.parent.parent.pin_to_net[self]

    def add_decoupling_capacitor(self, capacitor, net_name=None, ground_net_name="GND"):
        from earthground.components import Capacitor, Component, validate_net_names

        assert isinstance(
            self.parent, Component
        ), "Component must be in a design before adding decoupling capacitor!"
        design = self.parent.parent
        if not isinstance(capacitor, Capacitor):
            raise TypeError(
                f"add_decoupling_capacitor() argument 'capacitor' must be a "
                f"Capacitor, got {type(capacitor).__name__}"
            )
        names = {"ground_net_name": ground_net_name}
        if net_name is not None:
            names["net_name"] = net_name
        validate_net_names("add_decoupling_capacitor()", **names)
        net_name = design._get_net_name_from_pin(self) if net_name is None else net_name
        design.add_component(capacitor)
        design.join_net(self, net_name)
        design.join_net(capacitor.pins[1], net_name)
        design.join_net(capacitor.pins[2], ground_net_name)


class PinContainer:
    def __init__(self, pins: Optional[List[Pin]] = None):
        pins = pins or []
        self._pins = tuple(pins)
        self.names = {p.name: p for p in pins}
        self.indicies = {p.index: p for p in pins}

    @classmethod
    def from_dict(cls, pin_dict, parent):
        pins = []
        for index, value in pin_dict.items():
            spec = (
                value
                if isinstance(value, BasePinSpec)
                else UnspecifiedPinSpec(name=value)
            )
            pins.append(Pin(spec.name, index, parent, spec))
        return cls(pins)

    @classmethod
    def from_list(cls, pin_list, parent):
        return cls([Pin(name, index, parent) for index, name in enumerate(pin_list)])

    @classmethod
    def from_count(
        cls,
        pin_count: int,
        parent,
        spec_class: type[BasePinSpec] = UnspecifiedPinSpec,
    ):
        return cls(
            [
                Pin(
                    str(index),
                    index,
                    parent,
                    spec_class(name=str(index)),
                )
                for index in range(1, pin_count + 1)
            ]
        )

    def __getitem__(self, index):
        return self.by_index(index)

    def __iter__(self) -> Pin:
        return iter(self._pins)

    def __len__(self):
        return len(self._pins)

    def by_name(self, name):
        if name in self.names:
            return self.names[name]
        raise ValueError(f"Unknown name: {name} in {self.names.keys()}")

    def by_index(self, index):
        if index in self.indicies:
            return self.indicies[index]
        raise ValueError(f"Unknown index: {index} in {self.indicies}")

    def all_with_name(self, name: Union[str, List[str]]):
        pins = []
        if not isinstance(name, (str, list)):
            raise ValueError("'name' must be a str or list of str!")
        for pin in self._pins:
            if isinstance(name, str) and pin.name == name:
                pins.append(pin)
            elif isinstance(name, list) and pin.name in name:
                pins.append(pin)
        return pins


def pin_sort_key(pin: Pin) -> tuple:
    name = pin.name
    try:
        return (0, int(name))
    except ValueError:
        if name.upper() in ("GND", "SHIELD"):
            return (2, name.upper())
        return (1, name.upper())
