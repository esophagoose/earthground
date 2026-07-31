import pathlib
from typing import List, Optional, Union, overload

import kiutils.footprint as kfp
import kiutils.utils.sexpr as sexpr_utils
import pygerber.aperture as ap_lib

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


def _aperture_from_kicad_pad(pad: kfp.Pad) -> ap_lib.Aperture:
    """Convert KiCad pad geometry into Earthground's aperture model."""
    width = pad.size.X
    height = pad.size.Y
    rotation = pad.position.angle or 0

    if pad.shape == "circle":
        return ap_lib.ApertureCircle(diameter=width)
    if pad.shape == "roundrect":
        radius = (pad.roundrectRatio or 0) * min(width, height)
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

    Stores the original S-expression for verbatim KiCad export and exposes
    electrical pad geometry through earthground's internal pad model.
    """

    def __init__(self, library: str, footprint_name: str, sexp: str):
        super().__init__()
        self.name = footprint_name
        self.description = footprint_name
        self.sexp = sexp

        parsed = sexpr_utils.parse_sexp(self.sexp)
        kicad_fp = kfp.Footprint.from_sexpr(parsed)
        for pad in kicad_fp.pads:
            if not pad.number or pad.type == "np_thru_hole":
                continue
            self.pads[pad.number] = ft.Pad(
                location=[pad.position.X, pad.position.Y],
                aperture=_aperture_from_kicad_pad(pad),
            )

    def get_bbox(self) -> BoundingBox:
        """Return the electrical pad bounds, or a small padless fallback."""
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
