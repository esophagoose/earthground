import logging
import math
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from typing import Optional, Union

SI_MAP = {
    "p": Decimal("1e-12"),
    "n": Decimal("1e-9"),
    "u": Decimal("1e-6"),
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
    logging.info(f"Voltage divider: {vsupply}V -> {vout}V, R1: {r1}, R2: {r2}")
    logging.info(f"Output voltage: Expected {vout}V, Actual {vout_actual}V")
    logging.info(f"Error: {error:.2f}%")
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
        si_reversed = {v: k for k, v in SI_MAP.items()}
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


def is_either_none(value1, value2):
    return value1 is None or value2 is None


VALID_VB_TYPES = Union[float, "ValueBounds"]


@dataclass(frozen=True)
class ValueBounds:
    units: str
    min: Optional[VALID_VB_TYPES] = None
    typ: Optional[VALID_VB_TYPES] = None
    max: Optional[VALID_VB_TYPES] = None

    def to_list(self):
        return [self.min, self.typ, self.max]

    def __str__(self):
        return (
            f"{self.min}{self.units} < {self.typ}{self.units} < {self.max}{self.units}"
        )

    def _negate(self):
        return ValueBounds(
            units=self.units, min=-self.max, typ=-self.typ, max=-self.min
        )

    def __add__(self, other: VALID_VB_TYPES) -> "ValueBounds":
        """Add two ValueBounds objects or a ValueBounds and a number."""
        if isinstance(other, ValueBounds):
            if self.units != other.units:
                raise ValueError(
                    f"Cannot add values with different units: {self.units} and {other.units}"
                )
            values = [other.min, other.typ, other.max]
        else:
            values = [other, other, other]

        return ValueBounds(
            units=self.units,
            min=None if is_either_none(self.min, values[0]) else self.min + values[0],
            typ=None if is_either_none(self.typ, values[1]) else self.typ + values[1],
            max=None if is_either_none(self.max, values[2]) else self.max + values[2],
        )

    def __radd__(self, other):
        """Support addition when ValueBounds is on the right side."""
        return self.__add__(other)

    def __sub__(self, other):
        """Subtract two ValueBounds objects or a number from a ValueBounds."""
        if isinstance(other, ValueBounds):
            if self.units != other.units:
                raise ValueError(
                    f"Cannot subtract values with different units: {self.units} and {other.units}"
                )
            return self.__add__(other._negate())
        elif isinstance(other, (int, float)):
            return self.__add__(-other)

    def __rsub__(self, other):
        """Support subtraction when ValueBounds is on the right side."""
        if isinstance(other, (int, float)):
            return ValueBounds(
                units=self.units,
                min=None if self.max is None else other - self.max,
                typ=None if self.typ is None else other - self.typ,
                max=None if self.min is None else other - self.min,
            )
        else:
            return NotImplemented

    def __mul__(self, other):
        """Multiply a ValueBounds by another ValueBounds or a number."""
        if isinstance(other, ValueBounds):
            # For multiplication, we combine the units
            new_units = (
                f"{self.units}·{other.units}"
                if self.units and other.units
                else self.units or other.units
            )

            # Calculate all possible combinations for min and max
            if self.min is not None and other.min is not None:
                products = [
                    self.min * other.min,
                    self.min * (other.max if other.max is not None else other.min),
                    (self.max if self.max is not None else self.min) * other.min,
                    (self.max if self.max is not None else self.min)
                    * (other.max if other.max is not None else other.min),
                ]
                new_min = min(products)
                new_max = max(products)
            else:
                new_min = None
                new_max = None

            return ValueBounds(
                units=new_units,
                min=new_min,
                typ=(
                    None
                    if self.typ is None or other.typ is None
                    else self.typ * other.typ
                ),
                max=new_max,
            )
        elif isinstance(other, (int, float)):
            # For scalar multiplication
            if other >= 0:
                return ValueBounds(
                    units=self.units,
                    min=None if self.min is None else self.min * other,
                    typ=None if self.typ is None else self.typ * other,
                    max=None if self.max is None else self.max * other,
                )
            else:
                # When multiplying by a negative number, min and max swap
                return ValueBounds(
                    units=self.units,
                    min=None if self.max is None else self.max * other,
                    typ=None if self.typ is None else self.typ * other,
                    max=None if self.min is None else self.min * other,
                )
        else:
            return NotImplemented

    def __rmul__(self, other):
        """Support multiplication when ValueBounds is on the right side."""
        return self.__mul__(other)

    def __truediv__(self, other):
        """Divide a ValueBounds by another ValueBounds or a number."""
        if isinstance(other, ValueBounds):
            # For division, we combine the units
            new_units = (
                f"{self.units}/{other.units}"
                if self.units and other.units
                else self.units
            )

            # We need to handle division by zero or near-zero values
            if (
                other.min is not None
                and other.min <= 0
                and (other.max is None or other.max >= 0)
            ):
                raise ValueError("Division could result in division by zero")

            # Calculate all possible combinations for min and max
            if self.min is not None and other.min is not None and other.min != 0:
                quotients = []
                if other.min != 0:
                    quotients.append(self.min / other.min)
                if other.max is not None and other.max != 0:
                    quotients.append(self.min / other.max)
                if self.max is not None:
                    if other.min != 0:
                        quotients.append(self.max / other.min)
                    if other.max is not None and other.max != 0:
                        quotients.append(self.max / other.max)

                if quotients:
                    new_min = min(quotients)
                    new_max = max(quotients)
                else:
                    new_min = None
                    new_max = None
            else:
                new_min = None
                new_max = None

            return ValueBounds(
                units=new_units,
                min=new_min,
                typ=(
                    None
                    if self.typ is None or other.typ is None or other.typ == 0
                    else self.typ / other.typ
                ),
                max=new_max,
            )
        elif isinstance(other, (int, float)):
            if other == 0:
                raise ValueError("Division by zero")

            if other > 0:
                return ValueBounds(
                    units=self.units,
                    min=None if self.min is None else self.min / other,
                    typ=None if self.typ is None else self.typ / other,
                    max=None if self.max is None else self.max / other,
                )
            else:
                # When dividing by a negative number, min and max swap
                return ValueBounds(
                    units=self.units,
                    min=None if self.max is None else self.max / other,
                    typ=None if self.typ is None else self.typ / other,
                    max=None if self.min is None else self.min / other,
                )
        else:
            return NotImplemented

    def __rtruediv__(self, other):
        """Support division when ValueBounds is on the right side."""
        if isinstance(other, (int, float)):
            # We need to handle division by zero or near-zero values
            if (
                self.min is not None
                and self.min <= 0
                and (self.max is None or self.max >= 0)
            ):
                raise ValueError("Division could result in division by zero")

            # Calculate all possible combinations
            quotients = []
            if self.min is not None and self.min != 0:
                quotients.append(other / self.min)
            if self.max is not None and self.max != 0:
                quotients.append(other / self.max)

            if quotients:
                new_min = min(quotients)
                new_max = max(quotients)
            else:
                new_min = None
                new_max = None

            return ValueBounds(
                units=f"1/{self.units}" if self.units else "",
                min=new_min,
                typ=None if self.typ is None or self.typ == 0 else other / self.typ,
                max=new_max,
            )
        else:
            return NotImplemented

    def validate(self, value):
        assert self.min <= value <= self.max, f"Value {value} is out of bounds: {self}"
