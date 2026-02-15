import math
from typing import TYPE_CHECKING, Dict, NamedTuple, Tuple

import earthground.components as cmp
from earthground.footprint_types import BoundingBox

if TYPE_CHECKING:
    import earthground.schematic as sch_lib


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
        self.layout_count = 2
        self.traces = []
        self.vias = []
        self.pours = []

    def flatten(self) -> Dict[str, Tuple[ComponentLayout, cmp.Component]]:
        """
        Flatten the layout into a dictionary of component layouts.
        """
        flattened = {}
        print(f"Flattening layout for {self.design.name}")
        for cid, component in self.design.components.items():
            print(f"Component: {cid} {type(component)}")
            if isinstance(component, cmp.ModuleComponent):
                module_position = self.placement[cid].component
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
                flattened[cid] = (self.placement[cid], component)
            else:
                raise ValueError(f"Invalid component type: {type(component)}")
        return flattened
