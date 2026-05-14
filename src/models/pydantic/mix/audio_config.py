from __future__ import annotations

from pydantic import BaseModel, Field


class AudioConfig(BaseModel):
    start: float = Field(ge=0, default=0)
    end: float = Field(default=-1)
    offset: float = Field(default=0, ge=0)
    volume: float = Field(default=1, ge=0, le=20)
    weight: float = Field(default=1, ge=0, le=1)
