from collections.abc import Iterator, Mapping
from types import MappingProxyType

import earthground.standard_values as sv

# Canonical keys get dimensional validation. Part-specific snake-case keys remain valid.
RATING_DIMENSIONS = {
    "vcc": "V",
    "v_supply": "V",
    "vin": "V",
    "vout": "V",
    "vi": "V",
    "vi_o": "V",
    "v_il": "V",
    "v_ih": "V",
    "v_ol": "V",
    "v_oh": "V",
    "vref_a": "V",
    "vref_b": "V",
    "v_en": "V",
    "vik": "V",
    "esd_hbm": "V",
    "i_out": "A",
    "i_channel": "A",
    "i_ik": "A",
    "i_pass": "A",
    "i_ih": "A",
    "i_cc": "A",
    "ta": "°C",
    "tj": "°C",
    "tstg": "°C",
    "ci_ref": "F",
    "ci_en": "F",
    "cio_off": "F",
    "cio_on": "F",
    "r_pull_up": "Ω",
    "r_pull_down": "Ω",
}


class Ratings(Mapping[str, sv.ValueBounds]):
    """Immutable, canonically keyed electrical specifications."""

    def __init__(self, values=None, **kwargs):
        combined = dict(values or {})
        combined.update(kwargs)
        checked = {}
        for key, value in combined.items():
            if not isinstance(key, str) or not key or key != key.strip().lower():
                raise ValueError(f"Rating key must be canonical snake-case: {key!r}")
            if any(not (char.isalnum() or char == "_") for char in key):
                raise ValueError(f"Rating key must be canonical snake-case: {key!r}")
            expected = RATING_DIMENSIONS.get(key)
            sv.require_bounds(value, expected, f"Rating {key!r}")
            checked[key] = value
        self._values = MappingProxyType(checked)

    def __getitem__(self, key: str) -> sv.ValueBounds:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"Ratings({self._values!r})"
