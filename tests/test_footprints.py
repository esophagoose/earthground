import pygerber.aperture as ap_lib
import pytest

from earthground.footprints.generics import SinglePad
from earthground.footprints.header import (PointOneInchHeader,
                                           TwoRowThroughHoleHeader)
from earthground.footprints.passives import PassivePackage, PassiveSmd
from earthground.footprints.qfn import PackageSize, Qfn
from earthground.footprints.tssop import TSSOP, Pitch, Width

FOOTPRINTS = [
    (SinglePad, {"aperture": ap_lib.ApertureRectangle(0.5, 0.5)}),
    (TwoRowThroughHoleHeader, {"count": 10}),
    (PointOneInchHeader, {"count": 10}),
    (PassiveSmd, {"package": PassivePackage.C0402}),
    (Qfn, {"pin_count": 24, "size": PackageSize.S4_0MMx4_0MM, "pitch": 0.5}),
    (
        TSSOP,
        {
            "count": 24,
            "width": Width.W4_4MM,
            "pitch": Pitch.P0_5MM,
            "pad_size": (1.1, 0.85),
        },
    ),
]


@pytest.mark.parametrize("class_and_args", FOOTPRINTS)
def test_function(class_and_args):
    footprint, kwargs = class_and_args
    fp = footprint(**kwargs)
    assert fp
