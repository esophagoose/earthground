"""
KiCad IPC interface for earthground.

Uses the kipy library (kicad-python) to communicate with a running KiCad
instance over IPC sockets. Provides bidirectional sync of footprint positions
between an earthground Design and the KiCad PCB editor.

Requirements:
    - KiCad 9.0+ with the API server enabled (Preferences > Plugins)
    - pip install kicad-python
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from kipy import KiCad
from kipy.board import Board
from kipy.board_types import FootprintInstance
from kipy.geometry import Angle, Vector2

import earthground.components as cmp
import earthground.schematic as sch_lib


@dataclass
class FootprintPosition:
    """Position and orientation of a footprint on the board."""
    x_mm: float
    y_mm: float
    angle_deg: float = 0.0
    layer: str = "F.Cu"

    def to_vector2(self) -> Vector2:
        return Vector2.from_xy_mm(self.x_mm, self.y_mm)


@dataclass
class PositionUpdate:
    """A recorded position change for a footprint."""
    refdes: str
    old: FootprintPosition
    new: FootprintPosition


class KicadIpc:
    """Interface between an earthground Design and a live KiCad PCB editor.

    Connects to a running KiCad instance via IPC and provides methods to
    read and write footprint positions, keeping the earthground source
    Design in sync with the board layout.

    :param design: The earthground Design that corresponds to the open board.
    :param socket_path: Optional KiCad API socket path. If None, uses the
        default (``ipc:///tmp/kicad/api.sock`` on Unix, or the
        ``KICAD_API_SOCKET`` environment variable).

    Example::

        from earthground.ipc.kicad_ipc import KicadIpc

        ipc = KicadIpc(my_design)
        ipc.pull_positions()       # read positions from KiCad into design
        ipc.move("U1", 50.0, 25.0) # move U1 and push to KiCad
    """

    def __init__(self, design: sch_lib.Design, socket_path: Optional[str] = None):
        self.design = design
        kwargs = {}
        if socket_path:
            kwargs["socket_path"] = socket_path
        self._kicad = KiCad(**kwargs)
        self._board: Board = self._kicad.get_board()
        self._refdes_to_component: Dict[str, cmp.Component] = {}
        self._history: List[PositionUpdate] = []
        self._build_refdes_map()

    def _build_refdes_map(self):
        """Build a mapping from reference designator to earthground Component."""
        for module in self.design.modules + [self.design]:
            for component in module.components.values():
                if not component.virtual:
                    self._refdes_to_component[component.refdes] = component

    def _get_kicad_footprints(self) -> List[FootprintInstance]:
        """Fetch all footprints from the KiCad board."""
        return self._board.get_footprints()

    def _find_kicad_footprint(self, refdes: str) -> Optional[FootprintInstance]:
        """Find a KiCad footprint by its reference designator."""
        for fp in self._get_kicad_footprints():
            if fp.reference_field.text.value == refdes:
                return fp
        return None

    def _fp_position(self, fp: FootprintInstance) -> FootprintPosition:
        """Extract a FootprintPosition from a KiCad FootprintInstance."""
        pos = fp.position
        return FootprintPosition(
            x_mm=pos.x / 1_000_000,  # nanometers to mm
            y_mm=pos.y / 1_000_000,
            angle_deg=fp.orientation.degrees,
            layer=str(fp.layer),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_position(self, refdes: str) -> FootprintPosition:
        """Read the current position of a footprint from KiCad.

        :param refdes: Reference designator (e.g. "U1", "R3").
        :raises KeyError: If the refdes is not found on the board.
        :return: The footprint's current position.
        """
        fp = self._find_kicad_footprint(refdes)
        if fp is None:
            raise KeyError(f"Footprint '{refdes}' not found on the board")
        return self._fp_position(fp)

    def get_all_positions(self) -> Dict[str, FootprintPosition]:
        """Read positions of all footprints from KiCad.

        :return: Mapping of refdes to FootprintPosition.
        """
        result = {}
        for fp in self._get_kicad_footprints():
            ref = fp.reference_field.text.value
            result[ref] = self._fp_position(fp)
        return result

    def move(self, refdes: str, x_mm: float, y_mm: float,
             angle_deg: Optional[float] = None) -> PositionUpdate:
        """Move a footprint to an absolute position and push to KiCad.

        Also stores the position on the earthground Component so the source
        design stays in sync.

        :param refdes: Reference designator of the footprint to move.
        :param x_mm: Target X position in millimeters.
        :param y_mm: Target Y position in millimeters.
        :param angle_deg: Optional target orientation in degrees.
        :return: A PositionUpdate recording old and new positions.
        :raises KeyError: If the refdes is not found.
        """
        fp = self._find_kicad_footprint(refdes)
        if fp is None:
            raise KeyError(f"Footprint '{refdes}' not found on the board")

        old = self._fp_position(fp)
        fp.position = Vector2.from_xy_mm(x_mm, y_mm)
        if angle_deg is not None:
            fp.orientation = Angle.from_degrees(angle_deg)

        self._board.update_items([fp])

        new = FootprintPosition(
            x_mm=x_mm,
            y_mm=y_mm,
            angle_deg=angle_deg if angle_deg is not None else old.angle_deg,
            layer=old.layer,
        )
        self._store_position(refdes, new)

        update = PositionUpdate(refdes=refdes, old=old, new=new)
        self._history.append(update)
        return update

    def move_delta(self, refdes: str, dx_mm: float, dy_mm: float,
                   dangle_deg: float = 0.0) -> PositionUpdate:
        """Move a footprint by a relative offset and push to KiCad.

        :param refdes: Reference designator of the footprint to move.
        :param dx_mm: X offset in millimeters.
        :param dy_mm: Y offset in millimeters.
        :param dangle_deg: Rotation offset in degrees.
        :return: A PositionUpdate recording old and new positions.
        :raises KeyError: If the refdes is not found.
        """
        fp = self._find_kicad_footprint(refdes)
        if fp is None:
            raise KeyError(f"Footprint '{refdes}' not found on the board")

        old = self._fp_position(fp)
        fp.position += Vector2.from_xy_mm(dx_mm, dy_mm)
        if dangle_deg:
            fp.orientation += Angle.from_degrees(dangle_deg)

        self._board.update_items([fp])

        new = FootprintPosition(
            x_mm=old.x_mm + dx_mm,
            y_mm=old.y_mm + dy_mm,
            angle_deg=old.angle_deg + dangle_deg,
            layer=old.layer,
        )
        self._store_position(refdes, new)

        update = PositionUpdate(refdes=refdes, old=old, new=new)
        self._history.append(update)
        return update

    def pull_positions(self) -> Dict[str, FootprintPosition]:
        """Read all footprint positions from KiCad and store them on the
        corresponding earthground Components.

        This is useful after the user has manually arranged components in
        KiCad and wants those positions reflected in the source design.

        :return: Mapping of refdes to the pulled FootprintPosition.
        """
        positions = self.get_all_positions()
        for refdes, pos in positions.items():
            self._store_position(refdes, pos)
        return positions

    def push_positions(self, positions: Dict[str, FootprintPosition]):
        """Push a set of positions to KiCad, updating the board.

        :param positions: Mapping of refdes to desired FootprintPosition.
        :raises KeyError: If any refdes is not found on the board.
        """
        footprints_to_update = []
        for refdes, pos in positions.items():
            fp = self._find_kicad_footprint(refdes)
            if fp is None:
                raise KeyError(f"Footprint '{refdes}' not found on the board")
            fp.position = pos.to_vector2()
            fp.orientation = Angle.from_degrees(pos.angle_deg)
            footprints_to_update.append(fp)
            self._store_position(refdes, pos)
        self._board.update_items(footprints_to_update)

    def _store_position(self, refdes: str, pos: FootprintPosition):
        """Store a position on the earthground Component via its parameters dict."""
        if refdes in self._refdes_to_component:
            component = self._refdes_to_component[refdes]
            component.parameters["_position"] = {
                "x_mm": pos.x_mm,
                "y_mm": pos.y_mm,
                "angle_deg": pos.angle_deg,
                "layer": pos.layer,
            }

    @property
    def history(self) -> List[PositionUpdate]:
        """List of all position updates made through this interface."""
        return list(self._history)

    def refresh_board(self):
        """Re-fetch the board from KiCad.

        Call this if the board has been reloaded or changed externally.
        """
        self._board = self._kicad.get_board()
