"""
Layout module for earthground designs.

Provides data structures for component placement and board layer information,
and a Layout class that tracks placement of all components in a Design.
"""

import enum
from dataclasses import dataclass
from typing import Dict, Optional


class Layer(enum.Enum):
    """PCB layer for component placement."""
    TOP = "TOP"
    BOTTOM = "BOTTOM"


@dataclass
class Position:
    """2D position on the board in millimeters."""
    x: float = 0.0
    y: float = 0.0


@dataclass
class Placement:
    """Placement of a single component on the board."""
    id: str
    position: Position
    layer: Layer = Layer.TOP
    rotation: float = 0.0


class Layout:
    """Tracks component placements for a Design.

    Automatically populates a default grid placement for all non-virtual
    components. Placements can be overridden by assigning to
    ``layout.placement[refdes]``.

    :param design: The earthground Design to track placements for.
    """

    def __init__(self, design):
        self.placement: Dict[str, Placement] = {}
        self._build_default_placement(design)

    def _build_default_placement(self, design):
        """Create default grid placements for all components."""
        x_spacing = 10.0
        y_spacing = 50.0
        modules = design.modules + [design]
        for y, module in enumerate(modules):
            x_index = 0
            for component in module.components.values():
                if component.virtual:
                    continue
                self.placement[component.refdes] = Placement(
                    id=component.refdes,
                    position=Position(
                        x=x_spacing * (x_index + 1),
                        y=y_spacing * (y + 1),
                    ),
                    layer=Layer.TOP,
                )
                x_index += 1

    def to_dict(self) -> Dict[str, dict]:
        """Export placements as a plain dict (e.g. for YAML serialization)."""
        result = {}
        for refdes, p in self.placement.items():
            result[refdes] = {
                "x": p.position.x,
                "y": p.position.y,
                "layer": p.layer.value,
                "rotation": p.rotation,
            }
        return result
