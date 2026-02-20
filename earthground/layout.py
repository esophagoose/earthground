import logging
import math
from typing import TYPE_CHECKING, Dict, NamedTuple, Tuple

import earthground.components as cmp
from earthground.footprint_types import BoundingBox

if TYPE_CHECKING:
    import earthground.schematic as sch_lib


SCHEMATIC_WIDTH = 600


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


class ComponentLayout(NamedTuple):
    component: Position
    id: Position = Position(x=0, y=0, angle=0)


class Layout:
    def __init__(self, design: "sch_lib.Design") -> None:
        self.design = design
        self.placement: Dict[str, ComponentLayout] = {}
        self.outline = BoundingBox(x1=0, y1=0, x2=0, y2=0)
        self.layer_count = 2
        self.traces = []
        self.vias = []
        self.pours = []

    def get_placement(self, id: str) -> Dict[str, ComponentLayout]:
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
                component=Position(x=x, y=y, angle=0),
            )
        return self.placement[id]

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
