import enum
from collections import namedtuple

import pygerber.aperture as aperture

import earthground.footprint_types as ft

SIZES = [
    "0402",
    "0603",
    "0612",
    "0805",
    "0815",
    "1020",
    "1206",
    "1210",
    "1218",
    "1812",
    "2010",
    "2512",
    "2816",
    "4020",
]

PackageParams = namedtuple("PackageParams", ["x", "w", "h", "r"])


class PassivePackage(enum.Enum):
    R0402 = PackageParams(0.51, 0.54, 0.64, 0.25)
    R0603 = PackageParams(0.825, 0.8, 0.95, 0.25)
    R0612 = PackageParams(0.75, 1, 3.4, 0.25)
    R0805 = PackageParams(0.9125, 1.025, 1.4, 0.243902)
    R0815 = PackageParams(0.9375, 1.025, 4.05, 0.243902)
    R1020 = PackageParams(1.125, 1.15, 5.2, 0.217391)
    R1206 = PackageParams(1.4625, 1.125, 1.75, 0.222222)
    R1210 = PackageParams(1.4625, 1.125, 2.65, 0.222222)
    R1218 = PackageParams(1.475, 1.05, 4.75, 0.238095)
    R1812 = PackageParams(2.1375, 1.125, 3.4, 0.222222)
    R2010 = PackageParams(2.3125, 1.225, 2.65, 0.204082)
    R2512 = PackageParams(2.9625, 1.225, 3.35, 0.204082)
    R2816 = PackageParams(2.5125, 3.025, 4.45, 0.082645)
    R4020 = PackageParams(4.8125, 1.475, 5.3, 0.169492)

    C0402 = PackageParams(0.48, 0.56, 0.62, 0.25)
    C0504 = PackageParams(0.54, 0.66, 1.28, 0.25)
    C0603 = PackageParams(0.775, 0.9, 0.95, 0.25)
    C0805 = PackageParams(0.95, 1, 1.45, 0.25)
    C1206 = PackageParams(1.475, 1.15, 1.8, 0.217391)
    C1210 = PackageParams(1.475, 1.15, 2.7, 0.217391)
    C1812 = PackageParams(2.05, 1.4, 3.4, 0.178571)
    C1825 = PackageParams(2.05, 1.4, 6.8, 0.178571)
    C2220 = PackageParams(2.55, 1.8, 5.4, 0.138889)
    C2225 = PackageParams(2.5375, 1.625, 6.6, 0.153846)
    C3640 = PackageParams(4.0875, 1.925, 10.45, 0.12987)


class PassiveSmd(ft.BaseFootprint):
    def __init__(self, package: PassivePackage) -> None:
        super().__init__()
        self.name = package.name
        self.description = f"PASSIVE SMD {self.name}, IPC_7351 nominal"
        p = package.value
        pad = aperture.ApertureRectangle(p.w, p.h, p.r)
        self.pads = {
            1: ft.Pad(location=[-p.x, 0], aperture=pad),
            2: ft.Pad(location=[p.x, 0], aperture=pad),
        }


def get_passive_footprint(size, passive_type):
    assert size in SIZES, f"Invalid size: {size}; Options: {SIZES}"
    prefix = passive_type.refdes_prefix
    package = PassivePackage[f"{prefix}{size}"]
    return PassiveSmd(package)
