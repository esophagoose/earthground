import pathlib
import sys
from typing import List, Optional, Union

import kiutils.footprint as kfp
import kiutils.utils.sexpr as sexpr_utils
import pygerber.aperture as ap_lib

import earthground.footprint_types as ft
from earthground.footprint_types import BoundingBox

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
        additional_lib_paths: List[Union[str, pathlib.Path]] = [],
    ):
        """
        :param additional_lib_paths: Extra directories that contain ``*.pretty``
            footprint libraries (same layout as KiCad's ``footprints/`` root).
            These are searched before the default KiCad install path.
        """
        if not isinstance(additional_lib_paths, list):
            raise ValueError("additional_lib_paths must be a list")

        self.lib_paths: List[pathlib.Path] = []
        if additional_lib_paths:
            self.lib_paths.extend(pathlib.Path(p) for p in additional_lib_paths)
        self.lib_paths.append(pathlib.Path(DEFAULT_FOOTPRINT_PATH[sys.platform]))

    def get_footprint_path(self, library: str, footprint_name: str) -> pathlib.Path:
        library_path = library if library.endswith(".pretty") else f"{library}.pretty"
        footprint_path = (
            footprint_name
            if footprint_name.endswith(".kicad_mod")
            else f"{footprint_name}.kicad_mod"
        )
        for path in self.lib_paths:
            if (path / library_path / footprint_path).exists():
                return path / library_path / footprint_path
        raise FileNotFoundError(
            f"Footprint '{footprint_path}' or library '{library_path}' not found in path"
        )

    def import_footprint(
        self, library: str, footprint_name: str
    ) -> Optional[KicadFootprint]:
        with open(self.get_footprint_path(library, footprint_name), "r") as file:
            sexp = file.read()
            return KicadFootprint(library, footprint_name, sexp)
