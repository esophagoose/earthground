import enum
from typing import Tuple

import pygerber.aperture as ap_lib

import common.components as cmp
import common.footprint_types as ft


class PinLayout(enum.Enum):
    Z_FORMAT = enum.auto()  # [(1, 2), (3, 4), (5, 6)]
    ROW_FORMAT = enum.auto()  # [(1, 4), (2, 5), (3, 6)]


def standard_0_1_inch_header(pin_count, row_count=1):
    return Throughhole(pin_count, row_count).generate_footprint(
        ap_lib.ApertureCircle(diameter=1.4, hole=1.02),
        2.54,  # mm = 0.1 inch
        PinLayout.Z_FORMAT,
    )


class Throughhole(cmp.Component):
    def __init__(self, pin_count, row_count):
        super().__init__(refdes_prefix="J")
        assert pin_count % row_count == 0, "Unbalanced connector!"
        self.pin_count = pin_count
        self.row_count = row_count
        self.pins_per_row = int(pin_count / row_count)
        self.name = f"CONNECTOR_{self.pins_per_row}x{row_count}"
        self.description = self.name
        self.pins = cmp.PinContainer.from_count(pin_count, self)
        self.footprint = None

    def generate_footprint(self, aperture, spacing: float, layout_format: PinLayout):
        size = (self.pins_per_row, self.row_count)
        self.footprint = ConnectorFootprint(size, aperture, spacing, layout_format)
        return self


class ConnectorFootprint:
    def __init__(
        self, dimensions: Tuple[float], aperture, spacing, layout_format
    ) -> None:
        self.pins_per_row, self.rows = dimensions
        self.count = self.pins_per_row * self.rows
        self.aperture = aperture
        self.spacing = spacing
        self.format = layout_format
        self.refdes_prefix = "J"
        self.pads = {i: ft.Pad([x, y], aperture) for i, x, y in self.get_locations()}

    def get_locations(self):
        xstart = -(self.rows - 1) * self.spacing / 2
        ystart = -(self.pins_per_row - 1) * self.spacing / 2
        if self.format == PinLayout.ROW_FORMAT:
            for i in range(self.rows):
                for index in range(self.pins_per_row):
                    x = xstart + (i + self.spacing)
                    y = ystart + index * self.spacing
                    yield index + (i * self.pins_per_row) + 1, x, y
        elif self.format == PinLayout.Z_FORMAT:
            for index in range(self.pins_per_row):
                for i in range(self.rows):
                    x = xstart + (i * self.spacing)
                    y = ystart + index * self.spacing
                    yield (index * self.rows) + i + 1, x, y
        else:
            raise TypeError(f"Invalid layout format: {self.format}")
