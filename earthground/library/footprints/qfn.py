import enum
from collections import namedtuple
from typing import Optional, Tuple

import pygerber.aperture as ap_lib

import earthground.footprint_types as ft

VALID_PITCHES = [0.4, 0.5]
VALID_EP_SIZES = [1.45, (2.65, 2.65)]

PackageSizeType = namedtuple("PackageSizeType", ["aperture", "width"])


class PackageSize(enum.Enum):
    S2_5MMx2_5MM = "2.5mmx2.5mm"
    S3_0MMx3_0MM = "3mmx3mm"
    S4_0MMx4_0MM = "4mmx4mm"


PACKAGE_SIZES = {
    "2.5mmx2.5mm": PackageSizeType(
        width=2.525,
        aperture=ap_lib.ApertureRectangle(0.675, 0.25, radius=0.0625),
    ),
    "3mmx3mm": PackageSizeType(
        width=2.875,
        aperture=ap_lib.ApertureRectangle(0.875, 0.25, radius=0.0625),
    ),
    "4mmx4mm": PackageSizeType(
        width=3.875,
        aperture=ap_lib.ApertureRectangle(0.875, 0.25, radius=0.0625),
    ),
}


def validate(value, options):
    if value in options:
        return value
    raise ValueError(f"Invalid option: {value}. Options {options}")


class Qfn(ft.BaseFootprint):
    def __init__(
        self,
        pin_count,
        size: PackageSize,
        pitch: float,
        ep: Optional[Tuple[float, float]] = None,
    ) -> None:
        super().__init__()
        package = PACKAGE_SIZES[size.value]
        size_name = size.name.replace("_", ".")[1:].lower()
        self.name = f"QFN{pin_count}_{size_name}_P{pitch}mm"
        if ep:
            self.name += f"_EP{'x'.join([f'{i}mm' for i in ep])}"
        pitch = validate(pitch, VALID_PITCHES)
        ep = validate(ep, VALID_EP_SIZES)
        rotated = ap_lib.ApertureRectangle(
            width=package.aperture.width,
            height=package.aperture.height,
            radius=package.aperture.radius,
            rotation=90,
        )
        pads = {0: package.aperture, 90: rotated}
        self.pads = {
            i: ft.Pad([x, y], pads[r])
            for i, x, y, r in ft.get_quad_side_locations(
                pin_count, package.width, pitch
            )
        }
        self.count = pin_count
        self.pads.update({"EP": ft.Pad([0, 0], ap_lib.ApertureRectangle(*ep))})

    def __str__(self) -> str:
        return f"QFN<{self.count}>"

    def __repr__(self) -> str:
        return self.name
