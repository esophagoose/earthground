import dataclasses
import enum
import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, NamedTuple, Optional, Tuple

import yaml
from pydantic import ValidationError

import earthground.components as cmp
from earthground.footprint_types import BoundingBox
from earthground.models.layout_models import LayoutPlacementMap

if TYPE_CHECKING:
    import earthground.schematic as sch_lib


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


class ViaConfig(NamedTuple):
    location: Position
    net_name: str
    hole_size: float
    drill_size: float


class PourLayer(NamedTuple):
    net_name: str
    layer: int


class FabLine(NamedTuple):
    start: Position
    end: Position


class FabText(NamedTuple):
    text: str
    position: Position
    height: float = 1.0
    width: float = 1.0
    thickness: Optional[float] = None


class Layer(enum.Enum):
    TOP = enum.auto()
    BOTTOM = enum.auto()


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


class ComponentLayout(NamedTuple):
    id: Position
    id_orientation: Orientation
    component: Position
    layer: Layer = Layer.TOP


def round_to_nearest(x: float, step: float) -> float:
    """Round x to the nearest given float step."""
    return math.ceil(x / step) * step


class Layout:
    def __init__(self, design: "sch_lib.Design") -> None:
        self.design: sch_lib.Design = design
        self.placement: Dict[str, Placement] = {}
        self.outline: BoundingBox = BoundingBox(x1=0, y1=0, x2=0, y2=0)
        self.layer_count: int = 2
        self.traces: list[Any] = []
        self.vias: list[ViaConfig] = []
        self.pours: list[PourLayer] = []
        self.fab: list[FabLine | FabText] = []

    def get_placement(self, id: str) -> ComponentLayout:
        floating_components = list(
            set(self.design.components.keys()) - set(self.placement.keys())
        )
        if id not in self.placement and id not in self.design.components:
            raise ValueError(
                f"Cannot get placement for {id}. Component not in {self.design.name}"
            )
        elif id in floating_components:
            logging.warning(f"Component {id} is floating in {self.design.name}")
            index = floating_components.index(id)
            x = 0
            for f in floating_components[:index]:
                if self.design.components[f].virtual:
                    continue
                x += self.design.components[f].footprint.get_bbox().width() + 1
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
                logging.warning(f"Placement ID is set but ignored on modules: {id}")
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

        flattened = {}
        for cid, component in self.design.components.items():
            if isinstance(component, cmp.ModuleComponent):
                module_layout = self.get_placement(cid)
                module_position = module_layout.component
                flat_module = component.parent.layout.flatten()
                for module_cid, comp in flat_module.items():
                    layout, component = comp
                    rotated_component = rotate_position(
                        layout.component, module_position.angle
                    )
                    rotated_id = rotate_position(layout.id, module_position.angle)
                    layout = ComponentLayout(
                        id=rotated_id,
                        id_orientation=layout.id_orientation,
                        component=rotated_component.translate(
                            module_position.x, module_position.y
                        ),
                        layer=combine_layer(module_layout.layer, layout.layer),
                    )
                    flattened[f"{cid}_{module_cid}"] = (layout, component)
            elif isinstance(component, cmp.Component):
                flattened[cid] = (self.get_placement(cid), component)
            else:
                raise ValueError(f"Invalid component type: {type(component)}")
        unused_cids = list(
            set(self.placement.keys()) - set(self.design.components.keys())
        )
        if unused_cids:
            print(
                f"WARNING: Components in layout but not used in  {self.design.name}: {unused_cids}"
            )
        return flattened
