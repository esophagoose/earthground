import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


class TO252(ft.BaseFootprint):
    """TO-252 (DPAK) package footprint"""

    def __init__(self):
        super().__init__()
        self.name = "TO-252"
        self.description = "TO-252 (DPAK) Surface Mount Package"

        # TO-252
        #      2
        #   ┌─▀▀▀─┐
        #   │     │  Pin 1: left
        #   │     │  Pin 2: center (tab)
        #   └┰─┰─┰┘  Pin 3: right
        #    ╹   ╹
        #    1   3
        #
        # Following the TI NDP package outline: https://www.ti.com/lit/ml/mmsf021a/mmsf021a.pdf
        ep = ap_lib.ApertureRectangle(5.7, 5.5)
        pad = ap_lib.ApertureRectangle(2.15, 1.3)

        pitch = 2.285  # mm
        pad_center_offset = -4.38
        ep_center_offset = 2.285
        self.pads = {
            1: ft.Pad(location=[pad_center_offset, -pitch], aperture=pad),
            2: ft.Pad(location=[ep_center_offset, 0], aperture=ep),
            3: ft.Pad(location=[pad_center_offset, pitch], aperture=pad),
        }


class TO263(ft.BaseFootprint):
    """TO-263 (D²PAK) package footprint"""

    def __init__(self):
        super().__init__()
        self.name = "TO-263"
        self.description = "TO-263 (D²PAK) Surface Mount Package"

        # TO-263AA
        #      2
        #   ┌─▀▀▀─┐
        #   │     │  Pin 1: left
        #   │     │  Pin 2: center (tab)
        #   └┰─┰─┰┘  Pin 3: right
        #    ╹   ╹
        #    1   3
        #
        # Following the Richtek TO-263AA package outline: https://www.richtek.com/assets/podfiles/Footprint-TO-263.pdf
        ep = ap_lib.ApertureRectangle(10, 8.5)
        pad = ap_lib.ApertureRectangle(4.0, 1.75)

        pitch = 2.54  # mm
        pad_center_offset = -10.5

        self.pads = {
            1: ft.Pad(location=[pad_center_offset, -pitch], aperture=pad),
            2: ft.Pad(location=[0, 0], aperture=ep),
            3: ft.Pad(location=[pad_center_offset, pitch], aperture=pad),
        }
