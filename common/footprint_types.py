import math
from typing import Dict, NamedTuple

import pygerber.layers.aperture as ap_lib


class Pad(NamedTuple):
    location: list
    aperture: ap_lib.Aperture


class BaseFootprint:
    def __init__(self) -> None:
        if not getattr(self, "pads", None):
            self.pads: Dict[str, Pad] = {}

    def get_bbox(self):
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = 0, 0
        for pad in self.pads.values():
            if isinstance(pad.aperture, ap_lib.ApertureCircle):
                r = pad.aperture.r
                hw, hh = r, r
            elif isinstance(pad.aperture, ap_lib.ApertureRectangle):
                hw, hh = pad.aperture.width / 2, pad.aperture.height / 2
            min_x = min(min_x, pad.location[0] - hw)
            max_x = max(max_x, pad.location[0] + hw)
            min_y = min(min_y, pad.location[1] - hh)
            max_y = max(max_y, pad.location[1] + hh)
        return (min_x, min_y), (max_x, max_y)


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


def get_quad_side_locations(count, width, pitch):
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
    hcount = math.floor(count / 4)
    wcount = math.ceil(count / 4)
    assert 2 * hcount + 2 * wcount == count
    constant = abs(width) / 2
    for sign in [-1, 1]:
        i = 0
        for index in range(hcount):
            x = sign * constant
            start = -pitch * (hcount - 1) / 2
            y = start + index * pitch
            y = -sign * y
            yield index + i, x, y, 0
        i += hcount
        for index in range(wcount):
            start = -pitch * (wcount - 1) / 2
            x = start + index * pitch
            x = -sign * x
            y = -sign * constant
            yield index + i, x, y, 90
        i += wcount
