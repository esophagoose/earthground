import dataclasses
import enum
import logging
import math
from typing import TYPE_CHECKING, Dict, NamedTuple, Optional, Tuple

import earthground.components as cmp
from earthground.footprint_types import BoundingBox

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

class ComponentLayout(NamedTuple):
    id: Position
    id_orientation: Orientation
    component: Position

def round_to_nearest(x: float, step: float) -> float:
    """Round x to the nearest given float step."""
    return math.ceil(x / step) * step


class Layout:
    def __init__(self, design: "sch_lib.Design") -> None:
        self.design = design
        self.placement: Dict[str, Placement] = {}
        self.outline = BoundingBox(x1=0, y1=0, x2=0, y2=0)
        self.layer_count = 2
        self.traces = []
        self.vias = []
        self.pours = []

    def get_placement(self, id: str) -> ComponentLayout:
        floating_components = list(
            set(self.design.components.keys()) - set(self.placement.keys())
        )
        # import code; code.interact(local=dict(globals(), **locals()))
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
            )
        if not self.placement[id].id:
            return ComponentLayout(
                id=Position(x=0, y=0, angle=0),
                id_orientation=Orientation.CENTER,
                component=self.placement[id].position,
            )
        component = self.design.components[id]
        component_position = self.placement[id].position
        ref_id = self.placement[id].id
        x, y = 0, 0
        if ref_id in [Orientation.TOP, Orientation.BOTTOM]:
            y = round_to_nearest((component.footprint.get_bbox().height() + GRID_SIZE) / 2, GRID_SIZE)
            y *= (-1 * int(ref_id == Orientation.TOP))
            y *= (-1 * int(component_position.angle == 180))
        elif ref_id in [Orientation.LEFT, Orientation.RIGHT]:
            x = round_to_nearest((component.footprint.get_bbox().width() + GRID_SIZE) / 2, GRID_SIZE)
            x = -x if ref_id == Orientation.LEFT else x
        return ComponentLayout(
            id=Position(x=x, y=y, angle=component_position.angle),
            id_orientation=ref_id,
            component=component_position
        )

    def flatten(self) -> Dict[str, Tuple[ComponentLayout, cmp.Component]]:
        """
        Flatten the layout into a dictionary of component layouts.
        """
        flattened = {}
        for cid, component in self.design.components.items():
            if isinstance(component, cmp.ModuleComponent):
                module_position = self.get_placement(cid).component
                flat_module = component.parent.layout.flatten()
                for module_cid, comp in flat_module.items():
                    layout, component = comp
                    layout = ComponentLayout(
                        id=layout.id,
                        id_orientation=layout.id_orientation,
                        component=layout.component.translate(
                            module_position.x, module_position.y
                        ),
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
