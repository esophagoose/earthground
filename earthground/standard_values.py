import math

SI_MAP = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "": 1,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
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


class SiNumber:
    """Represents a number with a unit in the SI system."""

    def __init__(self, value, unit):
        if isinstance(value, str) and value.endswith(unit):
            value = value[: -len(unit)]
        self.value = self._convert_to_float(value)
        self.unit = unit

    def _convert_to_float(self, value):
        if isinstance(value, str):
            number, units = value[:-1], value[-1]
            if value[-1] in SI_MAP:
                return float(number) * SI_MAP[units]
            else:
                return float(value)
        elif isinstance(value, (int, float)):
            return value
        raise ValueError(f"Unsupported type: {value}")

    def __str__(self):
        si_reversed = {v: k for k, v in SI_MAP.items()}
        for key in sorted(si_reversed.keys(), reverse=True):
            if self.value >= key:
                return str(self.value / key) + si_reversed[key] + self.unit
        return str(self.value) + self.unit

    def __repr__(self):
        return self.__str__()
