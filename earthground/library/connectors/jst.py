from __future__ import annotations

import enum

import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.footprint_types as ft
from earthground.importers import kicad
from earthground.importers.kicad import KicadFootprint, KicadImporter
from earthground.library.protocols.serial import I2C


class JstFamily(enum.Enum):
    ACH = "ACH"
    AUH = "AUH"
    EH = "EH"
    GH = "GH"
    J2100 = "J2100"
    JWPF = "JWPF"
    LEA = "LEA"
    NV = "NV"
    PH = "PH"
    PUD = "PUD"
    SFH = "SFH"
    SH = "SH"
    SHD = "SHD"
    SHL = "SHL"
    SUR = "SUR"
    VH = "VH"
    XA = "XA"
    XAG = "XAG"
    XH = "XH"
    ZE = "ZE"
    ZH = "ZH"


class JstType(enum.Enum):
    TOP_ENTRY = "Vertical"
    SIDE_ENTRY = "Horizontal"


class JstConnector(cmp.Component):
    def __init__(self, pin_count: int, family: JstFamily, style: JstType):
        super().__init__(refdes_prefix="J")
        self.name = f"JST_{family.value}_{pin_count}P_{style.value}"
        self.mpn = self.name
        self.family = family.value
        self.style = style.value
        self.pin_count = pin_count
        self.manufacturer = "JST"
        self.description = f"CONN HEADER {pin_count}POS 2.5MM {style.value}"
        self.detailed_description = f"JST {family.value} series {pin_count}pin"
        self.pins = cmp.PinContainer.from_count(pin_count, self)
        self.footprint = kicad.KicadImporter().import_footprint(
            "Connector_JST", self.get_symbol()
        )

    def get_symbol(self) -> str:
        if self.family != JstFamily.SH.value:
            raise NotImplementedError(f"{self.family} family is not supported yet")
        pins = f"{self.pin_count:02d}"
        style = "BM" if self.style == JstType.TOP_ENTRY.value else "SM"
        return f"JST_{self.family}_{style}{pins}B-SRSS-TB_1x{pins}-1MP_P1.00mm_{self.style}.kicad_mod"
