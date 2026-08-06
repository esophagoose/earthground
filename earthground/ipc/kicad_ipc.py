"""
KiCad IPC interface for earthground.

Uses the kipy library (kicad-python) to communicate with a running KiCad
instance over IPC sockets. Provides bidirectional sync of footprint positions
between an earthground Design and the KiCad PCB editor.

Requirements:
    - KiCad 9.0+ with the API server enabled (Preferences > Plugins)
    - pip install kicad-python
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from kipy import KiCad
from kipy.board import Board
from kipy.board_types import FootprintInstance
from kipy.geometry import Angle, Vector2
from kipy.proto.board.board_types_pb2 import ViaType
from kipy.util.board_layer import canonical_name
from kipy.util.units import to_mm

import earthground.components as cmp
import earthground.layout as layout_lib
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


@dataclass(frozen=True)
class BoardSnapshot:
    positions: Dict[str, FootprintPosition]
    tracks: tuple[layout_lib.Track, ...]
    vias: tuple[layout_lib.ViaConfig, ...]
    zones: tuple[layout_lib.Zone, ...]


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
            x_mm=to_mm(pos.x),
            y_mm=to_mm(pos.y),
            angle_deg=fp.orientation.degrees,
            layer=canonical_name(fp.layer),
        )

    @staticmethod
    def _net_name(item, *, owner: str) -> str:
        net = getattr(item, "net", None)
        name = getattr(net, "name", None)
        if not name:
            raise ValueError(f"{owner} is not assigned to a named net")
        return cmp.validate_net_name(name, owner=owner)

    @staticmethod
    def _point(point) -> layout_lib.LayoutPoint:
        return layout_lib.LayoutPoint(to_mm(point.x), to_mm(point.y))

    @classmethod
    def _polyline_points(cls, polyline) -> tuple[layout_lib.LayoutPoint, ...]:
        points = getattr(polyline, "points", None)
        if points is None:
            points = []
            for node in polyline:
                if hasattr(node, "has_point"):
                    if not node.has_point:
                        raise ValueError(
                            "Zones with curved outline segments cannot be written "
                            "to layout YAML"
                        )
                    points.append(node.point)
                else:
                    points.append(node)
        result = tuple(cls._point(point) for point in points)
        if len(result) > 1 and result[0] == result[-1]:
            result = result[:-1]
        return result

    @classmethod
    def _track(cls, item) -> layout_lib.Track:
        common = {
            "start": cls._point(item.start),
            "end": cls._point(item.end),
            "width": to_mm(item.width),
            "layer": canonical_name(item.layer),
            "net_name": cls._net_name(item, owner="KiCad track"),
            "locked": bool(getattr(item, "locked", False)),
        }
        if hasattr(item, "mid"):
            return layout_lib.TrackArc(mid=cls._point(item.mid), **common)
        return layout_lib.TrackSegment(**common)

    @classmethod
    def _via(cls, item) -> layout_lib.ViaConfig:
        via_type = getattr(item, "type", 0)
        if int(via_type) != ViaType.VT_THROUGH:
            raise ValueError("Only through vias can be written to layout YAML")
        return layout_lib.ViaConfig(
            location=layout_lib.Position(
                to_mm(item.position.x), to_mm(item.position.y), 0
            ),
            net_name=cls._net_name(item, owner="KiCad via"),
            hole_size=to_mm(item.diameter),
            drill_size=to_mm(item.drill_diameter),
        )

    @classmethod
    def _zone(cls, item) -> layout_lib.Zone:
        if item.is_rule_area():
            raise ValueError("Rule-area zones cannot be written to layout YAML")
        if len(item.layers) != 1:
            raise ValueError(
                "Only single-layer copper zones can be written to layout YAML"
            )
        outline = item.outline
        holes = getattr(outline, "holes", ())
        if holes:
            raise ValueError(
                "Zones with polygon holes cannot be written to layout YAML"
            )
        outer = getattr(outline, "outline", outline)
        points = cls._polyline_points(outer)
        if len(points) < 3:
            raise ValueError("KiCad zone outline must contain at least three points")
        return layout_lib.Zone(
            net_name=cls._net_name(item, owner="KiCad zone"),
            layers=(canonical_name(item.layers[0]),),
            outline=points,
            name=getattr(item, "name", None) or None,
            clearance=to_mm(item.clearance) if item.clearance is not None else 0.5,
            min_thickness=(
                to_mm(item.min_thickness) if item.min_thickness is not None else 0.25
            ),
            priority=int(getattr(item, "priority", 0)),
            fill=bool(getattr(item, "filled", True)),
            locked=bool(getattr(item, "locked", False)),
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

    def get_board_snapshot(self) -> BoardSnapshot:
        """Read editable placement and copper geometry from the open board."""
        return BoardSnapshot(
            positions=self.get_all_positions(),
            tracks=tuple(self._track(item) for item in self._board.get_tracks()),
            vias=tuple(self._via(item) for item in self._board.get_vias()),
            zones=tuple(self._zone(item) for item in self._board.get_zones()),
        )

    def move(
        self, refdes: str, x_mm: float, y_mm: float, angle_deg: Optional[float] = None
    ) -> PositionUpdate:
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

    def move_delta(
        self, refdes: str, dx_mm: float, dy_mm: float, dangle_deg: float = 0.0
    ) -> PositionUpdate:
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
