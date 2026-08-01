import logging
import math
import enum
import re
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from typing import Optional, Union

log = logging.getLogger(__name__)

SI_MAP = {
    "p": Decimal("1e-12"),
    "n": Decimal("1e-9"),
    "u": Decimal("1e-6"),
    "µ": Decimal("1e-6"),
    "μ": Decimal("1e-6"),
    "m": Decimal("1e-3"),
    "": Decimal("1"),
    "k": Decimal("1e3"),
    "M": Decimal("1e6"),
    "G": Decimal("1e9"),
}

STANDARD_VALUE_EXCEPTIONS = {
    "E24": {
        2.6: 2.7,
        2.9: 3.0,
        3.2: 3.3,
        3.5: 3.6,
        3.8: 3.9,
        4.2: 4.3,
        4.6: 4.7,
        8.3: 8.2,
    },
    "E192": {9.19: 9.20},
}


def get_standard_values(E=24):
    """
    Gets the standard values for a given step or "E" count using the formula. Unfortunately,
    there's some errors in the standard which are corrected by 'STANDARD_VALUE_EXCEPTIONS'.

    Definition: https://en.wikipedia.org/wiki/E_series_of_preferred_numbers
    """
    name = f"E{E}"
    sigfig = 1 if E < 48 else 2
    values = [round(math.pow(10**i, 1 / E), sigfig) for i in range(E)]
    for old, new in STANDARD_VALUE_EXCEPTIONS.get(name, {}).items():
        values[values.index(old)] = new
    return values


def find_closest_value(value, E=24):
    standard_values = get_standard_values(E)
    magnitude = int(math.log10(value))
    normalized_value = value / 10**magnitude
    diff = min(standard_values, key=lambda x: abs(x - normalized_value))
    return 10**magnitude * diff


def find_closest_ratio(ratio, E=24):
    standard_values = get_standard_values(E)
    closest = None
    diff = float("inf")
    for value1 in standard_values:
        for value2 in standard_values:
            current_ratio = value1 / value2
            current_diff = abs(current_ratio - ratio)
            if current_diff < diff:
                diff = current_diff
                closest = (value1, value2)
    return sorted(closest, reverse=(ratio < 1))


def voltage_divider(
    vsupply: float, vout: float, desired_resistance: float = 1.0
) -> tuple[float, float]:
    """
    Calculate resistor values for a voltage divider.

    Args:
        vsupply: Supply voltage
        vout: Desired output voltage
        desired_resistance: Desired total resistance (R1 + R2) in ohms

    Returns:
        Tuple of (R1, R2) resistor values in ohms
    """
    # Vout = Vsupply * R2 / (R1 + R2)
    # Solving for R2: R2 = Vout * (R1 + R2) / Vsupply
    # Let R_total = R1 + R2 = desired_resistance
    # R2 = Vout * R_total / Vsupply
    # R1 = R_total - R2

    r_total = desired_resistance
    r2 = find_closest_value(vout * r_total / vsupply)
    r1 = find_closest_value(r_total - r2)
    vout_actual = vsupply * r2 / (r1 + r2)
    error = abs(vout - vout_actual) / vout * 100
    log.debug("Voltage divider: %sV -> %sV, R1: %s, R2: %s", vsupply, vout, r1, r2)
    log.debug(
        "Output voltage: expected %sV, actual %sV",
        vout,
        vout_actual,
    )
    if error > 3:
        log.warning(
            "Voltage divider error %.2f%% exceeds 3%% for %sV -> %sV",
            error,
            vsupply,
            vout,
        )
    else:
        log.debug("Error: %.2f%%", error)
    return (r1, r2)


class SiNumber:
    """Represents a number with a unit in the SI system."""

    def __init__(self, value, unit):
        if isinstance(value, str) and value.endswith(unit):
            value = value[: -len(unit)]
        self.value = self._convert_to_decimal(value)
        self.unit = unit

    def _convert_to_decimal(self, value):
        if isinstance(value, str):
            number, units = value[:-1], value[-1]
            try:
                if value[-1] in SI_MAP:
                    return Decimal(number) * SI_MAP[units]
                return Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(f"Unsupported type: {value}") from exc
        elif isinstance(value, int):
            return Decimal(value)
        elif isinstance(value, float):
            return Decimal(str(value))
        elif isinstance(value, Decimal):
            return value
        raise ValueError(f"Unsupported type: {value}")

    def __str__(self):
        si_reversed = {
            Decimal("1e-12"): "p",
            Decimal("1e-9"): "n",
            Decimal("1e-6"): "u",
            Decimal("1e-3"): "m",
            Decimal("1"): "",
            Decimal("1e3"): "k",
            Decimal("1e6"): "M",
            Decimal("1e9"): "G",
        }
        for key in sorted(si_reversed.keys(), reverse=True):
            if self.value >= key:
                return (
                    self._format_decimal(self.value / key)
                    + si_reversed[key]
                    + self.unit
                )
        return self._format_decimal(self.value) + self.unit

    def __repr__(self):
        return self.__str__()

    def __float__(self):
        return float(self.value)

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        normalized = value.normalize()
        if normalized == normalized.to_integral():
            return format(normalized.quantize(Decimal("1")), "f")

        text = format(normalized, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text


class CheckStatus(enum.Enum):
    PASS = "Pass"
    FAIL = "Fail"
    UNKNOWN = "Unknown"


class BoundDirection(enum.Enum):
    LOWER = "lower"
    UPPER = "upper"


class IndeterminateBoundsError(ValueError):
    pass


class _Unbounded:
    def __repr__(self):
        return "UNBOUNDED"


UNBOUNDED = _Unbounded()

VALID_VB_TYPES = Union[int, float, Decimal, str, SiNumber, "ValueBounds"]

_NUMBER_RE = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"\s*([pnumkMGµμ]?)([A-Za-z°Ω/·²]*)\s*$"
)
_UNIT_ALIASES = {
    "": "",
    "V": "V",
    "A": "A",
    "W": "W",
    "F": "F",
    "H": "H",
    "s": "s",
    "m": "m",
    "week": "week",
    "weeks": "week",
    "Hz": "Hz",
    "Ω": "Ω",
    "ohm": "Ω",
    "R": "Ω",
    "°C": "°C",
    "C": "°C",
    "°C/W": "°C/W",
}

_SCALED_UNIT_ALIASES = {
    "mil": ("m", Decimal("0.0000254"), "mil"),
    "mils": ("m", Decimal("0.0000254"), "mil"),
}


def _normalize_unit(units: str) -> tuple[str, Decimal, str, bool]:
    """Return canonical unit, magnitude scale, display unit, and opacity."""
    units = units.replace(" ", "")
    if units in _SCALED_UNIT_ALIASES:
        canonical, scale, display = _SCALED_UNIT_ALIASES[units]
        return canonical, scale, display, False
    if units in _UNIT_ALIASES:
        canonical = _UNIT_ALIASES[units]
        return canonical, Decimal(1), canonical, False
    for prefix in ("p", "n", "u", "µ", "μ", "m", "k", "M", "G"):
        if not units.startswith(prefix):
            continue
        base = units[len(prefix) :]
        if base in _UNIT_ALIASES and _UNIT_ALIASES[base] not in ("", "°C", "°C/W"):
            canonical = _UNIT_ALIASES[base]
            display_prefix = "µ" if prefix in ("u", "μ") else prefix
            return canonical, SI_MAP[prefix], display_prefix + canonical, False
    # Unknown compound dimensions remain usable only when their strings match exactly.
    return units, Decimal(1), units, True


def _source_tuple(source) -> tuple[str, ...]:
    if source is None:
        return ()
    if isinstance(source, str):
        return (source,)
    return tuple(dict.fromkeys(str(item) for item in source))


def _merge_sources(*sources: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for source in sources for item in source))


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


@dataclass(frozen=True, init=False)
class ValueBounds:
    """A unit-normalized datasheet interval with independently unknown fields."""

    units: str
    min: Optional[Decimal]
    typ: Optional[Decimal]
    max: Optional[Decimal]
    source: tuple[str, ...]
    display_units: str
    opaque_dimension: bool

    def __init__(
        self,
        units: str,
        min=None,
        typ=None,
        max=None,
        source=None,
    ):
        canonical, scale, display, opaque = _normalize_unit(units)
        lower = self._coerce(min, canonical, scale, endpoint="min")
        typical = self._coerce(typ, canonical, scale, endpoint="typ")
        upper = self._coerce(max, canonical, scale, endpoint="max")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"Minimum {lower} exceeds maximum {upper}")
        if typical is not None:
            if lower is not None and typical < lower:
                raise ValueError(f"Typical {typical} is below minimum {lower}")
            if upper is not None and typical > upper:
                raise ValueError(f"Typical {typical} exceeds maximum {upper}")
        object.__setattr__(self, "units", canonical)
        object.__setattr__(self, "min", lower)
        object.__setattr__(self, "typ", typical)
        object.__setattr__(self, "max", upper)
        object.__setattr__(self, "source", _source_tuple(source))
        object.__setattr__(self, "display_units", display)
        object.__setattr__(self, "opaque_dimension", opaque)

    @staticmethod
    def _coerce(value, canonical, scale, endpoint):
        if value is None:
            return None
        if isinstance(value, ValueBounds):
            if value.units != canonical:
                raise ValueError(f"Incompatible units: {value.units} and {canonical}")
            return getattr(value, endpoint)
        if value is UNBOUNDED:
            if endpoint == "min":
                return Decimal("-Infinity")
            if endpoint == "max":
                return Decimal("Infinity")
            raise ValueError("UNBOUNDED cannot be used as a typical value")
        if isinstance(value, SiNumber):
            value_unit, value_scale, _, opaque = _normalize_unit(value.unit)
            if opaque or value_unit != canonical:
                raise ValueError(f"Incompatible units: {value.unit} and {canonical}")
            return value.value * value_scale
        if isinstance(value, str):
            match = _NUMBER_RE.match(value)
            if not match:
                raise ValueError(f"Unsupported value: {value}")
            number, prefix, suffix = match.groups()
            if suffix:
                parsed_unit, parsed_scale, _, opaque = _normalize_unit(prefix + suffix)
                if opaque or parsed_unit != canonical:
                    raise ValueError(
                        f"Incompatible units: {prefix + suffix} and {canonical}"
                    )
                return Decimal(number) * parsed_scale
            return Decimal(number) * (SI_MAP[prefix] if prefix else scale)
        return _decimal(value) * scale

    @classmethod
    def _from_canonical(
        cls,
        units,
        min=None,
        typ=None,
        max=None,
        source=(),
        display_units=None,
        opaque_dimension=False,
    ):
        instance = object.__new__(cls)
        object.__setattr__(instance, "units", units)
        object.__setattr__(instance, "min", min)
        object.__setattr__(instance, "typ", typ)
        object.__setattr__(instance, "max", max)
        object.__setattr__(instance, "source", _source_tuple(source))
        object.__setattr__(instance, "display_units", display_units or units)
        object.__setattr__(instance, "opaque_dimension", opaque_dimension)
        return instance

    @classmethod
    def from_tolerance(cls, nominal, pct, units, source=None):
        canonical, scale, display, opaque = _normalize_unit(units)
        typical = cls._coerce(nominal, canonical, scale, endpoint="typ")
        tolerance = typical * _decimal(pct) / Decimal(100)
        return cls._from_canonical(
            canonical,
            min=typical - tolerance,
            typ=typical,
            max=typical + tolerance,
            source=_source_tuple(source),
            display_units=display,
            opaque_dimension=opaque,
        )

    def to_list(self):
        return [self.min, self.typ, self.max]

    def __str__(self):
        scale = _normalize_unit(self.display_units)[1]

        def render(value):
            if value is None:
                return "?"
            if value.is_infinite():
                return "-∞" if value < 0 else "∞"
            return SiNumber._format_decimal(value / scale)

        return (
            f"{render(self.min)}{self.display_units} < "
            f"{render(self.typ)}{self.display_units} < "
            f"{render(self.max)}{self.display_units}"
        )

    def __eq__(self, other):
        if not isinstance(other, ValueBounds):
            return NotImplemented
        return (
            self.units,
            self.min,
            self.typ,
            self.max,
            self.opaque_dimension,
        ) == (
            other.units,
            other.min,
            other.typ,
            other.max,
            other.opaque_dimension,
        )

    def __hash__(self):
        return hash((self.units, self.min, self.typ, self.max, self.opaque_dimension))

    def _require_compatible(self, other):
        if self.units != other.units or (
            self.opaque_dimension != other.opaque_dimension
        ):
            raise ValueError(
                f"Cannot combine values with different units: "
                f"{self.units} and {other.units}"
            )

    def _coerce_scalar(self, value):
        display_scale = _normalize_unit(self.display_units)[1]
        return self._coerce(value, self.units, display_scale, endpoint="typ")

    def covers(self, other) -> CheckStatus:
        if isinstance(other, ValueBounds):
            self._require_compatible(other)
            if self.min is not None and other.min is not None and other.min < self.min:
                return CheckStatus.FAIL
            if self.max is not None and other.max is not None and other.max > self.max:
                return CheckStatus.FAIL
            if None not in (self.min, self.max, other.min, other.max):
                return CheckStatus.PASS
            return CheckStatus.UNKNOWN
        value = self._coerce_scalar(other)
        if self.min is not None and value < self.min:
            return CheckStatus.FAIL
        if self.max is not None and value > self.max:
            return CheckStatus.FAIL
        if self.min is not None and self.max is not None:
            return CheckStatus.PASS
        return CheckStatus.UNKNOWN

    def overlaps(self, other) -> CheckStatus:
        if not isinstance(other, ValueBounds):
            raise TypeError("overlaps() requires ValueBounds")
        self._require_compatible(other)
        if self.max is not None and other.min is not None and self.max < other.min:
            return CheckStatus.FAIL
        if other.max is not None and self.min is not None and other.max < self.min:
            return CheckStatus.FAIL
        if None not in (self.min, self.max, other.min, other.max):
            return CheckStatus.PASS
        return CheckStatus.UNKNOWN

    def margin(self, value):
        value = self._coerce_scalar(value)
        return (
            None if self.min is None else value - self.min,
            None if self.max is None else self.max - value,
        )

    def worst_case(self, direction: BoundDirection | str):
        direction = BoundDirection(direction)
        return self.min if direction is BoundDirection.LOWER else self.max

    def __contains__(self, value):
        status = self.covers(value)
        if status is CheckStatus.UNKNOWN:
            raise IndeterminateBoundsError(f"Containment is unknown for {self}")
        return status is CheckStatus.PASS

    def _negate(self):
        return self._from_canonical(
            self.units,
            min=None if self.max is None else -self.max,
            typ=None if self.typ is None else -self.typ,
            max=None if self.min is None else -self.min,
            source=self.source,
            display_units=self.display_units,
            opaque_dimension=self.opaque_dimension,
        )

    def __add__(self, other: VALID_VB_TYPES) -> "ValueBounds":
        if isinstance(other, ValueBounds):
            self._require_compatible(other)
            lower, typical, upper = other.min, other.typ, other.max
            source = _merge_sources(self.source, other.source)
        else:
            scalar = self._coerce_scalar(other)
            lower = typical = upper = scalar
            source = self.source
        return self._from_canonical(
            self.units,
            min=None if self.min is None or lower is None else self.min + lower,
            typ=None if self.typ is None or typical is None else self.typ + typical,
            max=None if self.max is None or upper is None else self.max + upper,
            source=source,
            display_units=self.display_units,
            opaque_dimension=self.opaque_dimension,
        )

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, ValueBounds):
            return self.__add__(other._negate())
        if isinstance(other, (int, float, Decimal, str, SiNumber)):
            return self.__add__(-self._coerce_scalar(other))
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, (int, float, Decimal, str, SiNumber)):
            return self._negate().__add__(other)
        return NotImplemented

    @staticmethod
    def _product_unit(left, right):
        pair = (left, right)
        reverse_pair = (right, left)
        known = {
            ("V", "A"): "W",
            ("A", "A"): "A²",
            ("A²", "Ω"): "W",
            ("°C/W", "W"): "°C",
        }
        if pair in known:
            return known[pair], False
        if reverse_pair in known:
            return known[reverse_pair], False
        if not left:
            return right, False
        if not right:
            return left, False
        return f"{left}·{right}", True

    @staticmethod
    def _quotient_unit(left, right):
        known = {("V", "Ω"): "A"}
        if (left, right) in known:
            return known[(left, right)], False
        if left == right:
            return "", False
        if not right:
            return left, False
        return f"{left}/{right}", True

    @staticmethod
    def _four_edges(left, right, operation):
        if None in (left.min, left.max, right.min, right.max):
            return None, None
        values = []
        for lhs in (left.min, left.max):
            for rhs in (right.min, right.max):
                try:
                    value = operation(lhs, rhs)
                except InvalidOperation:
                    continue
                if not value.is_nan():
                    values.append(value)
        if not values:
            return None, None
        return min(values), max(values)

    def __mul__(self, other):
        if isinstance(other, ValueBounds):
            units, opaque = self._product_unit(self.units, other.units)
            lower, upper = self._four_edges(self, other, lambda a, b: a * b)
            return self._from_canonical(
                units,
                min=lower,
                typ=(
                    None
                    if self.typ is None or other.typ is None
                    else self.typ * other.typ
                ),
                max=upper,
                source=_merge_sources(self.source, other.source),
                opaque_dimension=opaque,
            )
        if isinstance(other, (int, float, Decimal, str)):
            scalar = _decimal(other)
            lower = None if self.min is None else self.min * scalar
            upper = None if self.max is None else self.max * scalar
            if scalar < 0:
                lower, upper = upper, lower
            return self._from_canonical(
                self.units,
                min=lower,
                typ=None if self.typ is None else self.typ * scalar,
                max=upper,
                source=self.source,
                display_units=self.display_units,
                opaque_dimension=self.opaque_dimension,
            )
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, ValueBounds):
            if other.min is None or other.max is None or other.min <= 0 <= other.max:
                raise ValueError("Division could result in division by zero")
            units, opaque = self._quotient_unit(self.units, other.units)
            lower, upper = self._four_edges(self, other, lambda a, b: a / b)
            return self._from_canonical(
                units,
                min=lower,
                typ=(
                    None
                    if self.typ is None or other.typ is None
                    else self.typ / other.typ
                ),
                max=upper,
                source=_merge_sources(self.source, other.source),
                opaque_dimension=opaque,
            )
        if isinstance(other, (int, float, Decimal, str)):
            scalar = _decimal(other)
            if scalar == 0:
                raise ValueError("Division by zero")
            return self.__mul__(Decimal(1) / scalar)
        return NotImplemented

    def __rtruediv__(self, other):
        if not isinstance(other, (int, float, Decimal, str)):
            return NotImplemented
        if self.min is None or self.max is None or self.min <= 0 <= self.max:
            raise ValueError("Division could result in division by zero")
        scalar = _decimal(other)
        lower, upper = sorted((scalar / self.min, scalar / self.max))
        return self._from_canonical(
            f"1/{self.units}" if self.units else "",
            min=lower,
            typ=None if self.typ is None else scalar / self.typ,
            max=upper,
            source=self.source,
            opaque_dimension=bool(self.units),
        )

    def validate(self, value):
        assert (
            self.covers(value) is CheckStatus.PASS
        ), f"Value {value} is out of bounds or unknown: {self}"


def require_bounds(
    value,
    units: Optional[str],
    label: str,
    *,
    allow_none: bool = False,
) -> None:
    """Require a ValueBounds instance with the expected canonical dimension."""
    if value is None and allow_none:
        return
    if not isinstance(value, ValueBounds):
        raise TypeError(f"{label} must be ValueBounds")
    if units is not None and (value.units != units or value.opaque_dimension):
        raise ValueError(f"{label} must use {units}, got {value.units}")


def _unit_bounds(
    units,
    min=None,
    typ=None,
    max=None,
    *,
    nominal=None,
    tolerance_pct=None,
    source=None,
):
    if nominal is not None or tolerance_pct is not None:
        if (
            nominal is None
            or tolerance_pct is None
            or any(value is not None for value in (min, typ, max))
        ):
            raise ValueError(
                "nominal and tolerance_pct must be supplied together and without bounds"
            )
        return ValueBounds.from_tolerance(nominal, tolerance_pct, units, source)
    return ValueBounds(units=units, min=min, typ=typ, max=max, source=source)


def volts(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "V", min, typ, max, nominal=nominal, tolerance_pct=tolerance_pct, source=source
    )


def amps(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "A", min, typ, max, nominal=nominal, tolerance_pct=tolerance_pct, source=source
    )


def celsius(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "°C", min, typ, max, nominal=nominal, tolerance_pct=tolerance_pct, source=source
    )


def ohms(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "Ω", min, typ, max, nominal=nominal, tolerance_pct=tolerance_pct, source=source
    )


def farads(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "F", min, typ, max, nominal=nominal, tolerance_pct=tolerance_pct, source=source
    )


def watts(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "W", min, typ, max, nominal=nominal, tolerance_pct=tolerance_pct, source=source
    )


def weeks(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "week",
        min,
        typ,
        max,
        nominal=nominal,
        tolerance_pct=tolerance_pct,
        source=source,
    )


def millimeters(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "mm",
        min,
        typ,
        max,
        nominal=nominal,
        tolerance_pct=tolerance_pct,
        source=source,
    )


def mils(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "mil",
        min,
        typ,
        max,
        nominal=nominal,
        tolerance_pct=tolerance_pct,
        source=source,
    )


def celsius_per_watt(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "°C/W",
        min,
        typ,
        max,
        nominal=nominal,
        tolerance_pct=tolerance_pct,
        source=source,
    )


def ratio(
    min=None, typ=None, max=None, *, nominal=None, tolerance_pct=None, source=None
):
    return _unit_bounds(
        "", min, typ, max, nominal=nominal, tolerance_pct=tolerance_pct, source=source
    )
