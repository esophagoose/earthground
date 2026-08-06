import re
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

_COPPER_LAYER_PATTERN = re.compile(r"(?:F|B|In[1-9][0-9]*)\.Cu")


def normalize_copper_layer(value: object) -> str:
    layer = str(value).strip()
    lowered = layer.lower()
    if lowered == "f.cu":
        layer = "F.Cu"
    elif lowered == "b.cu":
        layer = "B.Cu"
    elif match := re.fullmatch(r"in([1-9][0-9]*)\.cu", lowered):
        layer = f"In{match.group(1)}.Cu"
    if not _COPPER_LAYER_PATTERN.fullmatch(layer):
        raise ValueError(f"Invalid copper layer '{layer}'")
    return layer


def _validate_net_name(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("net must be a string")
    value = value.strip()
    if not value:
        raise ValueError("net must not be empty")
    return value


class LayoutPlacementModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    layer: Literal["TOP", "BOTTOM"] = "TOP"
    x: float
    y: float
    rotation: float

    @field_validator("layer", mode="before")
    @classmethod
    def normalize_layer(cls, value: object) -> str:
        if value is None:
            return "TOP"

        layer = str(value).strip().upper()
        if layer not in {"TOP", "BOTTOM"}:
            raise ValueError(f"Invalid layer '{layer}'")
        return layer


class LayoutPlacementMap(RootModel[dict[str, LayoutPlacementModel]]):
    pass


class LayoutPointModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class _LayoutTrackBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    net: str
    layer: str
    width: float = Field(gt=0)
    locked: bool = False

    _normalize_layer = field_validator("layer", mode="before")(normalize_copper_layer)
    _validate_net = field_validator("net", mode="before")(_validate_net_name)


class LayoutTrackSegmentModel(_LayoutTrackBaseModel):
    type: Literal["segment"] = "segment"
    start: LayoutPointModel
    end: LayoutPointModel


class LayoutTrackArcModel(_LayoutTrackBaseModel):
    type: Literal["arc"] = "arc"
    start: LayoutPointModel
    mid: LayoutPointModel
    end: LayoutPointModel


LayoutTrackModel = Annotated[
    Union[LayoutTrackSegmentModel, LayoutTrackArcModel],
    Field(discriminator="type"),
]


class LayoutViaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    net: str
    position: LayoutPointModel
    diameter: float = Field(gt=0)
    drill: float = Field(gt=0)

    _validate_net = field_validator("net", mode="before")(_validate_net_name)

    @model_validator(mode="after")
    def validate_drill(self) -> "LayoutViaModel":
        if self.drill >= self.diameter:
            raise ValueError("via drill must be smaller than its diameter")
        return self


class LayoutZoneModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    net: str
    layers: list[str] = Field(min_length=1, max_length=1)
    outline: list[LayoutPointModel] = Field(min_length=3)
    name: str | None = None
    clearance: float = Field(default=0.5, ge=0)
    min_thickness: float = Field(default=0.25, gt=0)
    priority: int = Field(default=0, ge=0)
    fill: bool = True
    locked: bool = False

    _validate_net = field_validator("net", mode="before")(_validate_net_name)

    @field_validator("layers", mode="before")
    @classmethod
    def normalize_layers(cls, value: object) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            raise TypeError("zone layers must be a list")
        return [normalize_copper_layer(layer) for layer in value]


class LayoutFileModel(BaseModel):
    """Versioned layout sidecar, with compatibility for legacy placement maps."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    placements: dict[str, LayoutPlacementModel] = Field(default_factory=dict)
    tracks: list[LayoutTrackModel] | None = None
    vias: list[LayoutViaModel] | None = None
    zones: list[LayoutZoneModel] | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_placement_map(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        structured_keys = {"schema_version", "placements", "tracks", "vias", "zones"}
        if not value or not (structured_keys & set(value)):
            return {"schema_version": 1, "placements": value}
        return value
