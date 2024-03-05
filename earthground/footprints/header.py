import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class TwoRowThroughHoleHeader:
    def __init__(self, count: int, spacing: float = 2.54) -> None:
        self.name = f'Two Row 0.1" Header with {spacing} spacing'
        self.description = self.name
        self.pads = {}
        x = spacing / 2
        row_count = round(count / 2)
        for index, pad in PointOneInchHeader(row_count).pads.items():
            self.pads[index] = ft.Pad((-x, pad.location[1]), pad.aperture)
        for index, pad in PointOneInchHeader(row_count).pads.items():
            i = row_count + index
            self.pads[i] = ft.Pad((x, pad.location[1]), pad.aperture)


class PointOneInchHeader:
    def __init__(self, count: int, spacing: float = 2.54) -> None:
        self.name = f'0.1" Header, {count} Position, {spacing} Spacing'
        self.description = self.name
        start = -1 * spacing * ((count - 1) / 2)
        aperture = ap_lib.ApertureRectangle(2.54, 2.54)  # TODO: make this generic
        self.pads = {
            i: ft.Pad((0, i * spacing + start), aperture) for i in range(1, count + 1)
        }
