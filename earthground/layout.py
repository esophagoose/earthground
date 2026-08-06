import dataclasses
import enum
import logging
import math
from collections import namedtuple
from pathlib import Path
from typing import TYPE_CHECKING, Dict, NamedTuple, Optional, Tuple

import yaml

import earthground.components as cmp
from earthground.footprint_types import BoundingBox
from earthground.models.layout_models import (
    LayoutFileModel,
    LayoutTrackArcModel,
    LayoutTrackSegmentModel,
    normalize_copper_layer,
)

if TYPE_CHECKING:
    import earthground.schematic as sch_lib


log = logging.getLogger(__name__)


SCHEMATIC_WIDTH = 600
GRID_SIZE = 0.5
TEXT_HEIGHT = 1
TEXT_PADDING = 0.5


class Position(NamedTuple):
    x: float
    y: float
    angle: float

    def rotate(self, angle: float, origin: Tuple[float, float] = (0, 0)) -> "Position":
        """
        Return a new Position rotated by 'angle' radians about 'origin'.
        """
        if angle % 90 != 0:
            raise ValueError("Angle must be a multiple of 90 degrees")
        ox, oy = origin
        # Translate position to origin
        tx = self.x - ox
        ty = self.y - oy
        # Rotate
        cos_a = math.cos(math.radians(angle))
        sin_a = math.sin(math.radians(angle))
        rx = tx * cos_a - ty * sin_a
        ry = tx * sin_a + ty * cos_a
        # Translate back
        new_x = rx + ox
        new_y = ry + oy
        return Position(new_x, new_y, self.angle + angle)

    def translate(self, x: float, y: float) -> "Position":
        return Position(self.x + x, self.y + y, self.angle)


_ViaConfigBase = namedtuple(
    "ViaConfig",
    ["location", "net_name", "hole_size", "drill_size"],
)


class _ValidatedNetTuple:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        value = super().__new__(cls, *args, **kwargs)
        cmp.validate_net_name(value.net_name, owner=f"{cls.__name__}()")
        return value

    @classmethod
    def _make(cls, iterable):
        return cls(*tuple(iterable))

    def _replace(self, **kwargs):
        return type(self)(*super()._replace(**kwargs))


class ViaConfig(_ValidatedNetTuple, _ViaConfigBase):
    __slots__ = ()
    location: Position
    net_name: str
    hole_size: float
    drill_size: float


_PourLayerBase = namedtuple("PourLayer", ["net_name", "layer"])


class PourLayer(_ValidatedNetTuple, _PourLayerBase):
    __slots__ = ()
    net_name: str
    layer: int


@dataclasses.dataclass(frozen=True)
class LayoutPoint:
    x: float
    y: float


@dataclasses.dataclass(frozen=True)
class TrackSegment:
    start: LayoutPoint
    end: LayoutPoint
    width: float
    layer: str
    net_name: str
    locked: bool = False

    def __post_init__(self) -> None:
        cmp.validate_net_name(self.net_name, owner="TrackSegment()")
        if self.width <= 0:
            raise ValueError("TrackSegment width must be greater than 0")
        object.__setattr__(self, "layer", normalize_copper_layer(self.layer))


@dataclasses.dataclass(frozen=True)
class TrackArc:
    start: LayoutPoint
    mid: LayoutPoint
    end: LayoutPoint
    width: float
    layer: str
    net_name: str
    locked: bool = False

    def __post_init__(self) -> None:
        cmp.validate_net_name(self.net_name, owner="TrackArc()")
        if self.width <= 0:
            raise ValueError("TrackArc width must be greater than 0")
        object.__setattr__(self, "layer", normalize_copper_layer(self.layer))


Track = TrackSegment | TrackArc


@dataclasses.dataclass(frozen=True)
class Zone:
    net_name: str
    layers: tuple[str, ...]
    outline: tuple[LayoutPoint, ...]
    name: str | None = None
    clearance: float = 0.5
    min_thickness: float = 0.25
    priority: int = 0
    fill: bool = True
    locked: bool = False

    def __post_init__(self) -> None:
        cmp.validate_net_name(self.net_name, owner="Zone()")
        if len(self.layers) != 1:
            raise ValueError("Only single-layer copper zones are supported")
        if len(self.outline) < 3:
            raise ValueError("Zone outline must contain at least three points")
        if self.clearance < 0 or self.min_thickness <= 0 or self.priority < 0:
            raise ValueError(
                "Zone clearance and priority must be non-negative and minimum "
                "thickness must be greater than 0"
            )
        object.__setattr__(
            self,
            "layers",
            tuple(normalize_copper_layer(layer) for layer in self.layers),
        )


class Layer(enum.Enum):
    TOP = enum.auto()
    BOTTOM = enum.auto()


class FabLine(NamedTuple):
    start: Position
    end: Position
    layer: Layer = Layer.TOP


class SilkLine(NamedTuple):
    start: Position
    end: Position
    layer: Layer = Layer.TOP


class FabText(NamedTuple):
    text: str
    position: Position
    height: float = 1.0
    width: float = 1.0
    thickness: Optional[float] = None
    layer: Layer = Layer.TOP


class Orientation(enum.Enum):
    TOP = enum.auto()
    BOTTOM = enum.auto()
    LEFT = enum.auto()
    RIGHT = enum.auto()
    CENTER = enum.auto()


@dataclasses.dataclass
class Placement:
    position: Position
    id: Optional[Orientation] = None
    layer: Layer = Layer.TOP

    @classmethod
    def identity(cls, *, layer: Layer = Layer.TOP) -> "Placement":
        return cls(Position(0, 0, 0), layer=layer)


class ComponentLayout(NamedTuple):
    id: Position
    id_orientation: Orientation
    component: Position
    layer: Layer = Layer.TOP


class PlacementProvenance(enum.Enum):
    EXPLICIT = "Explicit"
    FALLBACK = "Fallback"


class FlattenedPlacement(NamedTuple):
    layout: ComponentLayout
    component: "cmp.Component"
    provenance: PlacementProvenance


def round_to_nearest(x: float, step: float) -> float:
    """Round x to the nearest given float step."""
    return math.ceil(x / step) * step


def combine_layer(parent_layer: Layer, child_layer: Layer) -> Layer:
    if parent_layer == Layer.TOP:
        return child_layer
    return Layer.BOTTOM if child_layer == Layer.TOP else Layer.TOP


def rotate_position(position: Position, angle: float) -> Position:
    rotation_radians = math.radians(angle)
    cos_a = math.cos(rotation_radians)
    sin_a = math.sin(rotation_radians)
    new_x = position.x * cos_a - position.y * sin_a
    new_y = position.x * sin_a + position.y * cos_a
    return Position(x=new_x, y=new_y, angle=position.angle + angle)


def transform_position(position: Position, origin: Position) -> Position:
    return rotate_position(position, origin.angle).translate(origin.x, origin.y)


class Layout:
    def __init__(self, design: "sch_lib.Design") -> None:
        self.design: sch_lib.Design = design
        self.placement: Dict[str, Placement] = {}
        self.outline: BoundingBox = BoundingBox(x1=0, y1=0, x2=0, y2=0)
        self.layer_count: int = 2
        self.tracks: list[Track] = []
        self.vias: list[ViaConfig] = []
        self.pours: list[PourLayer] = []
        self.zones: list[Zone] = []
        self.silk: list[SilkLine] = []
        self.fab: list[FabLine | FabText] = []

    @property
    def traces(self) -> list[Track]:
        """Compatibility alias for the formerly untyped trace collection."""
        return self.tracks

    @traces.setter
    def traces(self, value: list[Track]) -> None:
        self.tracks = value

    def get_placement(
        self, id: str, *, warn_on_fallback: bool = True
    ) -> ComponentLayout:
        floating_components = sorted(
            set(self.design.components.keys()) - set(self.placement.keys())
        )
        if id not in self.placement and id not in self.design.components:
            raise ValueError(
                f"Cannot get placement for {id}. Component not in {self.design.name}"
            )
        elif id in floating_components:
            if warn_on_fallback:
                log.warning("Component %s is floating in %s", id, self.design.name)
            index = floating_components.index(id)
            x = 0
            for f in floating_components[:index]:
                if self.design.components[f].virtual:
                    continue
                footprint = self.design.components[f].footprint
                x += (1 if footprint is None else footprint.get_bbox().width()) + 1
            x = x % SCHEMATIC_WIDTH
            y = x // SCHEMATIC_WIDTH
            return ComponentLayout(
                id=Position(x=0, y=0, angle=0),
                id_orientation=Orientation.CENTER,
                component=Position(x=x, y=y, angle=0),
                layer=Layer.TOP,
            )
        if id not in self.design.components:
            raise ValueError(
                f"Component {id} is not found in the design: {list(self.design.components.keys())}"
            )
        if not self.placement[id].id or self.design.components[id].virtual:
            if self.design.components[id].virtual and self.placement[id].id:
                log.warning("Placement ID is set but ignored on modules: %s", id)
            return ComponentLayout(
                id=Position(x=0, y=0, angle=0),
                id_orientation=Orientation.CENTER,
                component=self.placement[id].position,
                layer=self.placement[id].layer,
            )

        component = self.design.components[id]
        component_position = self.placement[id].position
        ref_id = self.placement[id].id
        angle = component_position.angle % 360
        x, y = 0, 0
        if ref_id in [Orientation.TOP, Orientation.BOTTOM]:
            # Vertical label offset from component origin
            y = round_to_nearest(
                (component.footprint.get_bbox().height() + GRID_SIZE) / 2,
                GRID_SIZE,
            )
            # Place above or below the component depending on reference edge
            y *= -1 if ref_id == Orientation.TOP else 1
            # Flip when the component is effectively upside-down (rotated past 90°)
            if 90 < angle < 270:
                y *= -1
        elif ref_id in [Orientation.LEFT, Orientation.RIGHT]:
            # Horizontal label offset from component origin
            x = round_to_nearest(
                (component.footprint.get_bbox().width() + GRID_SIZE) / 2,
                GRID_SIZE,
            )
            # Place left or right of the component depending on reference edge
            x *= -1 if ref_id == Orientation.LEFT else 1
            # Flip when the component is effectively upside-down so LEFT/RIGHT
            # stays visually attached to the same board-side edge.
            if 90 < angle < 270:
                x *= -1
        return ComponentLayout(
            id=Position(x=x, y=y, angle=component_position.angle),
            id_orientation=ref_id,
            component=component_position,
            layer=self.placement[id].layer,
        )

    def load_layout_from_yaml(self, path: str | Path) -> Dict[str, Placement]:
        with open(path, encoding="utf-8") as f:
            raw_layout = yaml.safe_load(f) or {}
        layout_file = LayoutFileModel.model_validate(raw_layout)

        placements = {
            refdes: Placement(
                position=Position(
                    x=placement.x,
                    y=placement.y,
                    angle=placement.rotation,
                ),
                id=None,
                layer=Layer[placement.layer],
            )
            for refdes, placement in layout_file.placements.items()
        }

        tracks: list[Track] | None = None
        if layout_file.tracks is not None:
            tracks = []
            for track in layout_file.tracks:
                common = {
                    "start": LayoutPoint(track.start.x, track.start.y),
                    "end": LayoutPoint(track.end.x, track.end.y),
                    "width": track.width,
                    "layer": track.layer,
                    "net_name": track.net,
                    "locked": track.locked,
                }
                if isinstance(track, LayoutTrackSegmentModel):
                    tracks.append(TrackSegment(**common))
                elif isinstance(track, LayoutTrackArcModel):
                    tracks.append(
                        TrackArc(
                            **common,
                            mid=LayoutPoint(track.mid.x, track.mid.y),
                        )
                    )
                else:  # pragma: no cover - protected by the discriminated union
                    raise TypeError(f"Unsupported track type: {type(track)}")

        vias = None
        if layout_file.vias is not None:
            vias = [
                ViaConfig(
                    location=Position(via.position.x, via.position.y, 0),
                    net_name=via.net,
                    hole_size=via.diameter,
                    drill_size=via.drill,
                )
                for via in layout_file.vias
            ]

        zones = None
        if layout_file.zones is not None:
            zones = [
                Zone(
                    net_name=zone.net,
                    layers=tuple(zone.layers),
                    outline=tuple(
                        LayoutPoint(point.x, point.y) for point in zone.outline
                    ),
                    name=zone.name,
                    clearance=zone.clearance,
                    min_thickness=zone.min_thickness,
                    priority=zone.priority,
                    fill=zone.fill,
                    locked=zone.locked,
                )
                for zone in layout_file.zones
            ]

        # Mutate only after the complete document has validated and converted.
        self.placement = placements
        if tracks is not None:
            self.tracks = tracks
        if vias is not None:
            self.vias = vias
        if zones is not None:
            self.zones = zones
            # Structured zones supersede legacy full-board pours.
            self.pours = []
        return placements

    def load_placements_from_yaml(self, path: str | Path) -> Dict[str, Placement]:
        """Load a legacy placement map or a versioned layout sidecar."""
        return self.load_layout_from_yaml(path)

    def flatten(self) -> Dict[str, Tuple[ComponentLayout, cmp.Component]]:
        """
        Flatten the layout into a dictionary of component layouts.
        """
        flattened = {
            refdes: (item.layout, item.component)
            for refdes, item in self.flatten_with_provenance().items()
        }
        unused_cids = list(
            set(self.placement.keys()) - set(self.design.components.keys())
        )
        if unused_cids:
            print(
                f"WARNING: Components in layout but not used in  {self.design.name}: {unused_cids}"
            )
        return flattened

    def flatten_with_provenance(
        self, *, warn_on_fallback: bool = True
    ) -> Dict[str, FlattenedPlacement]:
        """Flatten hierarchy while retaining whether every placement was explicit."""

        flattened: Dict[str, FlattenedPlacement] = {}

        def visit(design, prefix="", parent_layout=None, parent_explicit=True):
            for cid, component in design.components.items():
                refdes = f"{prefix}_{cid}" if prefix else cid
                local = design.layout.get_placement(
                    cid, warn_on_fallback=warn_on_fallback
                )
                explicit = parent_explicit and cid in design.layout.placement
                if parent_layout is not None:
                    local = ComponentLayout(
                        id=rotate_position(local.id, parent_layout.component.angle),
                        id_orientation=local.id_orientation,
                        component=transform_position(
                            local.component, parent_layout.component
                        ),
                        layer=combine_layer(parent_layout.layer, local.layer),
                    )
                if isinstance(component, cmp.ModuleComponent):
                    visit(component.parent, refdes, local, explicit)
                elif isinstance(component, cmp.Component):
                    flattened[refdes] = FlattenedPlacement(
                        local,
                        component,
                        (
                            PlacementProvenance.EXPLICIT
                            if explicit
                            else PlacementProvenance.FALLBACK
                        ),
                    )
                else:
                    raise ValueError(f"Invalid component type: {type(component)}")

        visit(self.design)
        return flattened

    def flatten_silk(self) -> list[SilkLine]:
        flattened = list(self.silk)
        for cid, component in self.design.components.items():
            if not isinstance(component, cmp.ModuleComponent):
                continue
            module_layout = self.get_placement(cid)
            module_position = module_layout.component
            for item in component.parent.layout.flatten_silk():
                flattened.append(
                    SilkLine(
                        start=transform_position(item.start, module_position),
                        end=transform_position(item.end, module_position),
                        layer=combine_layer(module_layout.layer, item.layer),
                    )
                )
        return flattened

    def flatten_fab(self) -> list[FabLine | FabText]:
        flattened: list[FabLine | FabText] = list(self.fab)
        for cid, component in self.design.components.items():
            if not isinstance(component, cmp.ModuleComponent):
                continue
            module_layout = self.get_placement(cid)
            module_position = module_layout.component
            for item in component.parent.layout.flatten_fab():
                layer = combine_layer(module_layout.layer, item.layer)
                if isinstance(item, FabLine):
                    flattened.append(
                        FabLine(
                            start=transform_position(item.start, module_position),
                            end=transform_position(item.end, module_position),
                            layer=layer,
                        )
                    )
                elif isinstance(item, FabText):
                    flattened.append(
                        FabText(
                            text=item.text,
                            position=transform_position(item.position, module_position),
                            height=item.height,
                            width=item.width,
                            thickness=item.thickness,
                            layer=layer,
                        )
                    )
                else:
                    raise TypeError(f"Unsupported fab item: {type(item)}")
        return flattened
