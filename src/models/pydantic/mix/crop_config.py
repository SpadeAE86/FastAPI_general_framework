from __future__ import annotations

from pydantic import BaseModel, Field


class CropConfig(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    translate_x: float = Field(default=0)
    translate_y: float = Field(default=0)
    rotation: float = Field(default=0)
    scale: float = Field(default=1, gt=0)
    mirror: bool = Field(default=False)
    speed: float = Field(default=1, gt=0)
    cap_cnt: int = Field(default=1, ge=0)
