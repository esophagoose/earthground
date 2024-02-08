import enum
import os
import random
from typing import Dict, Tuple

import pygerber.layers.aperture as aperture_lib
import pygerber.layers.gerber_layer as gl
import svgwrite as svg
import utils.tuples as tu
import yaml

import common.schematic as sch_lib
import common.stackup as su_lib


class ComponentLayer(enum.Enum):
    TOP = "TOP"
    BOTTOM = "BOTTOM"


def uppercase_hash(component):
    return "{:X}".format(hash(component) & (2**64 - 1))


class Layout:
    def __init__(self, schematic: sch_lib.Design, stackup: su_lib.Stackup) -> None:
        self.schematic = schematic
        self.stackup = stackup
        self.schematic.validate()
        self._pad_locations: Dict[str, Tuple[float, float]] = {}
        self._nets = []
        self._components = []

    def generate_layout(self, path: str):
        if not os.path.exists(path):
            self._create_yaml(path)
        components_locations = {}
        with open(path, "r") as file:
            components_locations = yaml.safe_load(file)
        for component in self.schematic.components.values():
            location = components_locations[component.refdes]
            self._components.append(
                [
                    component,
                    ComponentLayer(location["layer"]),
                    (location["x"], location["y"]),
                ]
            )

    def to_svg(self, path):
        renderer = LayoutSvg(self)
        renderer.save(path)

    def _create_yaml(self, path):
        output_data = {}
        comps = self.schematic.components.values()
        for component in sorted(comps, key=lambda c: c.refdes):
            key = component.refdes
            assert key not in output_data
            output_data[key] = {
                "description": component.description,
                "layer": ComponentLayer.TOP.value,
                "x": random.randint(0, 50),
                "y": random.randint(0, 50),
                "rotation": 0,
            }
        with open(path, "w") as file:
            yaml.safe_dump(output_data, file, sort_keys=False)


COLORS = {"base": "#333", "TOP,SILK": "yellow", "TOP,COPPER": "red"}


class LayoutSvg:
    def __init__(self, layout: Layout):
        self.regions = []
        self.operations = []
        self.multilayer = []
        self.canvas = svg.container.Group()
        self._color = None
        self._drill_down = False
        self._layer = None
        self._previous_point = (0, 0)
        self._pad_locations = {}

        for component, _, origin in layout._components:
            group = svg.container.Group()
            print(f"Adding footprint to svg: {component.footprint}")
            if component.refdes.startswith("U"):
                pt1, pt2 = component.footprint.get_bbox()
                point, w, h = tu.four_corner_rect(pt1[0], pt1[1], pt2[0], pt2[1])
                location = tu.add(pt1, origin)
                rect = svg.shapes.Rect(
                    insert=location, size=(w, h), fill_opacity=0
                ).fill("white")
                group.add(rect)
            for _, pad in component.footprint.pads.items():
                point = tu.add(pad.location, origin)
                state = gl.OperationState(
                    pad.aperture, None, point, [], True, None, None, None
                )
                group.add(self._flash_aperture(state))
            self.canvas.add(group)

    def save(self, filepath: str):
        drawing = svg.Drawing(filepath, profile="tiny")
        drawing.viewbox(width=50, height=50)
        drawing.add(self.canvas)
        drawing.save()

    def _flash_aperture(self, state: gl.OperationState):
        shape = state.aperture
        if isinstance(shape, aperture_lib.ApertureCircle):
            return svg.shapes.Circle(center=state.point, r=shape.r).fill("red")
        elif isinstance(shape, aperture_lib.ApertureRectangle):
            size = (shape.width, shape.height)
            x = state.point[0] - (shape.width / 2)
            y = state.point[1] - (shape.height / 2)
            r = shape.radius
            return svg.shapes.Rect(insert=(x, y), size=size, rx=r, ry=r).fill("red")
        elif isinstance(shape, aperture_lib.ApertureOutline):
            return svg.shapes.Polyline(points=shape.points).fill("red")
        else:
            raise NotImplementedError(shape)
