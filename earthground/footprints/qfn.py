import enum
from collections import namedtuple
from typing import Optional

import pygerber.aperture as ap_lib

import earthground.footprint_types as ft

VALID_PITCHES = [0.4, 0.5]

PackageSizeType = namedtuple("PackageSizeType", ["aperture", "width"])


class PackageSize(enum.Enum):
    S2_5MMx2_5MM = PackageSizeType(
        width=2.525,
        aperture=ap_lib.ApertureRectangle(0.675, 0.25, radius=0.0625),
    )
    S3_0MMx3_0MM = PackageSizeType(
        width=2.875,
        aperture=ap_lib.ApertureRectangle(0.875, 0.25, radius=0.0625),
    )
    S4_0MMx4_0MM = PackageSizeType(
        width=3.875,
        aperture=ap_lib.ApertureRectangle(0.875, 0.25, radius=0.0625),
    )
    S6_0MMx6_0MM = PackageSizeType(
        width=5.8,
        aperture=ap_lib.ApertureRectangle(0.65, 0.25, radius=0.0625),
    )


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
        ep: Optional[ft.EP] = None,
    ) -> None:
        super().__init__()
        package = size.value
        size_name = size.name.replace("_", ".")[1:].lower()
        self.name = f"QFN{pin_count}_{size_name}_P{pitch}mm"
        pitch = validate(pitch, VALID_PITCHES)
        pad_generator = ft.get_quad_side_locations(
            pin_count, package.width, pitch, package.aperture
        )
        self.pads = {i: pad for i, pad in pad_generator}
        self.count = pin_count
        if ep:
            self.name += f"_EP_{ep.aperture.width}mmx{ep.aperture.height}mm"
            self.pads.update({"EP": ft.Pad([0, 0], ep.aperture)})
