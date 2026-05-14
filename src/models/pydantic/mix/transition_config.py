from __future__ import annotations

from pydantic import BaseModel, Field


class TransitionConfig(BaseModel):
    transition_style: str = Field(default="fade", description="与 FFmpeg xfade 风格名一致")
    duration: float = Field(ge=0)
