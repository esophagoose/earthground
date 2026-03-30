from typing import Literal

from pydantic import BaseModel, ConfigDict, RootModel, field_validator


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
