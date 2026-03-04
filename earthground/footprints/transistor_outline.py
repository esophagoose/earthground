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


class TO277A(ft.BaseFootprint):
    """TO-277A (PSMC/SMPC) package footprint — flat power Schottky rectifier."""
    # TODO: Check footprint
    def __init__(self):
        super().__init__()
        self.name = "TO-277A"
        self.description = "TO-277A (PSMC/SMPC) Surface Mount Package, 2 pins + thermal pad"

        # TO-277A: 4.6 x 6.5 mm body, 1.1 mm height. Pitch 2.13 mm between pins 1 and 2.
        # Pin 1: Anode (left), Pin 2: Cathode (thermal pad), Pin 3: Anode (right)
        ep = ap_lib.ApertureRectangle(4.72, 4.8)
        pad = ap_lib.ApertureRectangle(1.4, 1.4)

        x_pitch = 1.925  # mm
        y_pitch = 1.04  # mm
        self.pads = {
            1: ft.Pad(location=[-x_pitch, -y_pitch], aperture=pad),
            2: ft.Pad(location=[x_pitch, 0], aperture=ep),
            3: ft.Pad(location=[-x_pitch, y_pitch], aperture=pad),
        }
