import dataclasses
import enum
import logging
import math
from collections import namedtuple
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, NamedTuple, Optional, Tuple

import yaml
from pydantic import ValidationError

import earthground.components as cmp
from earthground.footprint_types import BoundingBox
from earthground.models.layout_models import LayoutPlacementMap

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
        self.traces: list[Any] = []
        self.vias: list[ViaConfig] = []
        self.pours: list[PourLayer] = []
        self.silk: list[SilkLine] = []
        self.fab: list[FabLine | FabText] = []

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

    def load_placements_from_yaml(self, path: str | Path) -> Dict[str, Placement]:
        with open(path, encoding="utf-8") as f:
            raw_placements = yaml.safe_load(f) or {}
        placement_map = LayoutPlacementMap.model_validate(raw_placements)

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
            for refdes, placement in placement_map.root.items()
        }

        self.placement = placements
        return placements

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
