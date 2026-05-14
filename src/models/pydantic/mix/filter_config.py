from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class FilterConfig(BaseModel):
    type: str = Field(default="saturation", description="调色项类型")
    value: float = Field(default=0)
    angle: float = Field(default=0)


class VideoFilterConfig(BaseModel):
    filter_configs: List[Optional[FilterConfig]] = Field(default_factory=list)
    filter_template: Optional[str] = Field(default=None, description="预设模板名")
