import pathlib
import sys
from typing import List, Optional, Union

import kiutils.footprint as kfp
import kiutils.utils.sexpr as sexpr_utils

import earthground.footprint_types as ft
from earthground.footprint_types import BoundingBox

DEFAULT_FOOTPRINT_PATH = {
    "darwin": "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/",
    "linux": "/usr/share/kicad/modules/",
    "windows": "C:/Program Files/KiCad/share/kicad/modules/",
}


class KicadFootprint(ft.BaseFootprint):
    """
    Wrapper for a KiCad .kicad_mod footprint.

    Stores the original S-expression and lazily computes an approximate bounding
    box for placement using the KiCad pad geometry. Pads are not expanded into
    earthground's internal pad model because KiCad footprints are exported
    verbatim via kiutils in the KiCad exporter.
    """

    def __init__(self, library: str, footprint_name: str, sexp: str):
        super().__init__()
        self.name = footprint_name
        self.description = footprint_name
        self.sexp = sexp
        self._bbox: Optional[BoundingBox] = None

    def get_bbox(self) -> BoundingBox:
        """
        Approximate bounding box using the KiCad footprint pads.

        This avoids the default BaseFootprint implementation, which assumes
        an internal pad list and would return an invalid (inf) bounding box
        for imported KiCad footprints with no pads populated in earthground.
        """
        if self._bbox is not None:
            return self._bbox

        try:
            parsed = sexpr_utils.parse_sexp(self.sexp)
            kicad_fp = kfp.Footprint.from_sexpr(parsed)
        except Exception:
            # Fallback: treat as a small 1×1 mm symbol at the origin.
            self._bbox = BoundingBox(-0.5, -0.5, 0.5, 0.5)
            return self._bbox

        if not kicad_fp.pads:
            # No pads: use a conservative 1×1 mm box at origin.
            self._bbox = BoundingBox(-0.5, -0.5, 0.5, 0.5)
            return self._bbox

        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")

        for pad in kicad_fp.pads:
            pos = pad.position  # kiutils.items.common.Position
            size = pad.size  # Position(width, height)
            hw = size.X / 2.0
            hh = size.Y / 2.0
            min_x = min(min_x, pos.X - hw)
            min_y = min(min_y, pos.Y - hh)
            max_x = max(max_x, pos.X + hw)
            max_y = max(max_y, pos.Y + hh)

        # Sanity fallback if something went wrong in the loop.
        if not all(map(lambda v: v == v, [min_x, min_y, max_x, max_y])):  # NaN check
            self._bbox = BoundingBox(-0.5, -0.5, 0.5, 0.5)
        else:
            self._bbox = BoundingBox(min_x, min_y, max_x, max_y)

        return self._bbox


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
