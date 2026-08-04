import re
from decimal import Decimal

_POWER_NET_NAME_PATTERN = re.compile(r"([PN])(\d+)V(\d+)")


def voltage_to_net_name(voltage: float) -> str:
    value = Decimal(str(voltage))
    if not value.is_finite():
        raise ValueError(f"Cannot convert voltage '{voltage}' to a power net name")

    prefix = "P" if value >= 0 else "N"
    whole, separator, fractional = format(abs(value), "f").partition(".")
    fractional = fractional.rstrip("0") if separator else ""
    return f"{prefix}{whole}V{fractional or '0'}"


def power_net_name_to_voltage(net_name: str) -> float:
    match = _POWER_NET_NAME_PATTERN.fullmatch(net_name)
    if match is None:
        raise ValueError(f"Cannot convert net name '{net_name}' to a voltage")

    prefix, whole, fractional = match.groups()
    magnitude = float(f"{whole}.{fractional}")
    return magnitude if prefix == "P" else -magnitude
