import enum

import pygerber.gerber_layer as gl


class LayerType(enum.Enum):
    SIGNAL = "Signal"
    PLANE = "Plane"


class Plated(enum.Enum):
    PLATED = "P"
    NOT_PLATED = "N"


TWO_LAYER_STACKUP = [
    LayerType.SIGNAL,
    LayerType.SIGNAL,
]

FOUR_LAYER_STACKUP = [
    LayerType.SIGNAL,
    LayerType.SIGNAL,
    LayerType.PLANE,
    LayerType.SIGNAL,
]


class Stackup:
    def __init__(self, layers, edge_plating=Plated.NOT_PLATED) -> None:
        self.count = len(layers)
        self.board_outline = gl.GerberLayer()
        self.layers = layers
        self.layers = {
            "Legend,Top": gl.GerberLayer(),
            "Paste,Top": gl.GerberLayer(),
            "Soldermask,Top": gl.GerberLayer(),
            "Copper,L1": gl.GerberLayer(),
        }
        self.layers.update(
            {
                f"Copper,L{i+2},Inr,{l.value}": gl.GerberLayer()
                for i, l in enumerate(layers[1:-1])
            }
        )
        self.layers.update(
            {
                f"Copper,L{self.count},Bot,{layers[-1].value}": gl.GerberLayer(),
                "Soldermask,Bot": gl.GerberLayer(),
                "Paste,Bot": gl.GerberLayer(),
                "Legend,Bot": gl.GerberLayer(),
            }
        )
