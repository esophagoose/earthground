import pathlib
from typing import List, Optional, Union, overload

import pygerber.aperture as ap_lib
from pykicad import Footprint, read_from_string
import pykicad.models.pcb as pcb

import earthground.footprint_types as ft
from earthground.footprint_types import BoundingBox, KicadFootprintRef
from earthground.kicad.catalog import (
    KicadCatalogError,
    find_footprint_path,
    resolve_footprint_roots,
)

DEFAULT_FOOTPRINT_PATH = {
    "darwin": "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/",
    "linux": "/usr/share/kicad/modules/",
    "windows": "C:/Program Files/KiCad/share/kicad/modules/",
}


def _aperture_from_kicad_pad(pad: pcb.Pad) -> ap_lib.Aperture:
    """Convert KiCad pad geometry into Earthground's aperture model."""
    if pad.size is None:
        raise ValueError(f"KiCad pad {pad.number!r} has no size")
    width = pad.size.width
    height = pad.size.height
    rotation = pad.at.angle if pad.at is not None else 0

    if pad.shape == "circle":
        return ap_lib.ApertureCircle(diameter=width)
    if pad.shape == "roundrect":
        radius = (pad.roundrect_rratio or 0) * min(width, height)
        return ap_lib.ApertureRectangle(
            width=width,
            height=height,
            radius=radius,
            rotation=rotation,
        )
    if pad.shape == "oval":
        return ap_lib.ApertureRectangle.from_obround(
            width=width,
            height=height,
            rotation=rotation,
        )

    # Rectangles map exactly. Shapes without an equivalent Earthground
    # aperture (custom, trapezoid, chamfered rectangles, or future KiCad
    # shapes) are represented by their rotated bounding rectangle for
    # analysis. The original S-expression remains authoritative for export.
    return ap_lib.ApertureRectangle(
        width=width,
        height=height,
        rotation=rotation,
    )


class KicadFootprint(ft.BaseFootprint):
    """
    Wrapper for a KiCad .kicad_mod footprint.

    Parses the original S-expression once and caches the typed footprint model.
    The typed template is cached for direct placement by the KiCad exporter,
    while electrical pads are exposed through Earthground's footprint model.
    """

    def __init__(self, library: str, footprint_name: str, sexp: str):
        super().__init__()
        self.name = footprint_name
        self.description = footprint_name
        self.sexp = sexp
        document = read_from_string(sexp)
        if not isinstance(document.model, Footprint):
            raise TypeError("KiCad footprint text did not produce a Footprint")
        self.footprint = document.model
        for pad in self.footprint.pads:
            if not pad.number or pad.pad_type == "np_thru_hole" or pad.size is None:
                continue
            position = pad.at or pcb.Position(x=0, y=0)
            self.pads[pad.number] = ft.Pad(
                location=[position.x, position.y],
                aperture=_aperture_from_kicad_pad(pad),
            )

    def get_bbox(self) -> BoundingBox:
        """
        Approximate bounding box using the KiCad footprint pads.

        This avoids the default BaseFootprint implementation, which assumes
        an internal pad list and would return an invalid (inf) bounding box
        for imported KiCad footprints with no pads populated in earthground.
        """
        if not self.pads:
            # No pads: use a conservative 1×1 mm box at origin.
            return BoundingBox(-0.5, -0.5, 0.5, 0.5)
        return super().get_bbox()


class KicadImporter:
    def __init__(
        self,
        additional_lib_paths: Optional[List[Union[str, pathlib.Path]]] = None,
    ):
        """
        :param additional_lib_paths: Extra directories that contain ``*.pretty``
            footprint libraries (same layout as KiCad's ``footprints/`` root).
            These are searched before the default KiCad install path.
        """
        if additional_lib_paths is not None and not isinstance(
            additional_lib_paths, list
        ):
            raise ValueError("additional_lib_paths must be a list")

        self.lib_paths = list(
            resolve_footprint_roots(additional_lib_paths or [], initialize=False)
        )

    def get_footprint_path(self, library: str, footprint_name: str) -> pathlib.Path:
        try:
            return find_footprint_path(self.lib_paths, library, footprint_name)
        except KicadCatalogError as exc:
            raise FileNotFoundError(str(exc)) from exc

    @overload
    def import_footprint(
        self, library: KicadFootprintRef, footprint_name: None = None
    ) -> KicadFootprint: ...

    @overload
    def import_footprint(self, library: str, footprint_name: str) -> KicadFootprint: ...

    def import_footprint(
        self,
        library: Union[str, KicadFootprintRef],
        footprint_name: Optional[str] = None,
    ) -> KicadFootprint:
        if isinstance(library, KicadFootprintRef):
            if footprint_name is not None:
                raise TypeError(
                    "footprint_name must be omitted when importing a KicadFootprintRef"
                )
            footprint_name = library.footprint_name
            library = library.library
        if footprint_name is None:
            raise TypeError("footprint_name is required when library is a string")
        with open(self.get_footprint_path(library, footprint_name), "r") as file:
            sexp = file.read()
            return KicadFootprint(library, footprint_name, sexp)
