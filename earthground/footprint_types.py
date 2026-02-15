import math
from pathlib import Path
from typing import Dict, List, NamedTuple

import pygerber.aperture as ap_lib


class Pad(NamedTuple):
    location: list
    aperture: ap_lib.Aperture


class Point(NamedTuple):
    x: float
    y: float


class BoundingBox(NamedTuple):
    x1: float
    y1: float
    x2: float
    y2: float

    def width(self) -> float:
        return self.x2 - self.x1

    def height(self) -> float:
        return self.y2 - self.y1

    def center(self) -> Point:
        return Point((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


class BaseFootprint:
    def __init__(self) -> None:
        self.pads: Dict[str, Pad] = {}
        self.paste = 0  # None = no paste, 1 == 1mm reduction from pad
        self.silk = []
        self.vias: List[Point] = []

    def __str__(self):
        return self.name

    def get_bbox(self) -> BoundingBox:
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = 0, 0
        for pad in self.pads.values():
            if isinstance(pad.aperture, ap_lib.ApertureCircle):
                r = pad.aperture.r
                hw, hh = r, r
            elif isinstance(pad.aperture, ap_lib.ApertureRectangle):
                hw, hh = pad.aperture.width / 2, pad.aperture.height / 2
        return BoundingBox(
            min(min_x, pad.location[0] - hw),
            min(min_y, pad.location[1] - hh),
            max(max_x, pad.location[0] + hw),
            max(max_y, pad.location[1] + hh),
        )


class KicadFootprint(BaseFootprint):
    def __init__(self, kicad_mod: str, schematic, builtin: bool = True):
        super().__init__()
        self.kicad_mod = kicad_mod
        self.builtin = builtin
        self.schematic = schematic

    @property
    def path(self) -> Path:
        if self.builtin:
            print(Path(__file__).parent / "kicad-footprints" / self.kicad_mod)
            return (
                Path(__file__).parent.parent.parent
                / "kicad-footprints"
                / self.kicad_mod
            )
        else:
            return Path(self.kicad_mod)


class EP(NamedTuple):
    aperture: ap_lib.ApertureRectangle
    via_count: int


def get_dual_side_locations(count, width, pitch):
    """
    Generate x, y locations for footprint pads on a dual column IC.

            .-------.
        1 --|       |-- 8
        2 --|       |-- 7
        3 --|       |-- 6
        4 --|       |-- 5
            '_______'

    Args:
        count (int): Total pin count
        width (float): The width between the centers of the left and right pads
        pitch (float): The distance between each vertical pad

    Yields:
        tuple: A tuple containing the pad index and x, y coordinates of the pad location
    """
    for index in range(count):
        x_position = abs(width) / 2
        x = -x_position if index < count / 2 else x_position
        normalized_i = index % (count / 2)
        start = -pitch * ((count / 2) - 1) / 2
        y = start + normalized_i * pitch
        y = -y if index >= count / 2 else y
        yield index + 1, x, y


def get_quad_side_locations(
    count: int, width: float, pitch: float, pad: ap_lib.ApertureRectangle
):
    """
    Generate x, y locations for footprint pads on a quad column IC.

              12 11 10
              |  |  |
            .---------.
        1 --|         |-- 9
        2 --|         |-- 8
        3 --|         |-- 7
            '_________'
              |  |  |
              4  5  6

    Args:
        count (int): Total pin count
        width (float): The width between the centers of the left and right pads
        pitch (float): The distance between each vertical pad

    Yields:
        tuple: A tuple containing the pad index and x, y coordinates of the pad location
    """
    rotated = ap_lib.ApertureRectangle(
        width=pad.height,
        height=pad.width,
        radius=pad.radius,
        rotation=pad.rotation + 90,
    )
    hcount = math.floor(count / 4)
    wcount = math.ceil(count / 4)
    assert 2 * hcount + 2 * wcount == count
    constant = abs(width) / 2
    i = 1
    for sign in [-1, 1]:
        for index in range(hcount):
            x = sign * constant
            start = -pitch * (hcount - 1) / 2
            y = start + index * pitch
            y = -sign * y
            yield index + i, Pad([x, y], pad)
        i += hcount
        for index in range(wcount):
            start = -pitch * (wcount - 1) / 2
            x = start + index * pitch
            x = -sign * x
            y = -sign * constant
            yield index + i, Pad([x, y], rotated)
        i += wcount
