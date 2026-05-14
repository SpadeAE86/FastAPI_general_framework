from __future__ import annotations

from pydantic import BaseModel, Field


class StickerConfig(BaseModel):
    start: float = Field(ge=0, default=0, description="绝对起始时间（秒）")
    end: float = Field(default=-1, description="绝对结束时间（秒）")
    scale: float = Field(default=1.0, gt=0)
