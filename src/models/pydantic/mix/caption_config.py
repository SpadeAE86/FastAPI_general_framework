from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _is_hex_color(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    t = s.strip().lstrip("#")
    return bool(re.fullmatch(r"[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", t))


class Word(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start: int = Field(ge=0, alias="from")
    end: int = Field(ge=0, alias="to")
    font_size: Optional[int] = None
    font_type: Optional[str] = None
    color: Optional[str] = None
    outline_color: Optional[str] = None
    outline_width: Optional[int] = None

    @field_validator("color", "outline_color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v and not _is_hex_color(v):
            raise ValueError("字幕颜色需要形如 #RRGGBB 或 #RRGGBBAA")
        return v


class Cap(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    cap: str
    rotation: float = Field(default=0)
    absolute_x: Optional[float] = None
    absolute_y: Optional[float] = None
    outline_width: Optional[float] = Field(ge=0, default=None)
    scale: float = Field(default=1, gt=0, lt=5)
    font_size: Optional[int] = Field(default=54)
    font_type: Optional[str] = None
    color: Optional[str] = None
    outline_color: Optional[str] = None
    background_color: Optional[str] = None
    background_type: int = Field(ge=0, default=0)
    line_spacing: int = Field(ge=0, default=0)
    letter_spacing: int = Field(ge=0, default=0)
    word_config: List[Word] = Field(default_factory=list)


class CapConfig(BaseModel):
    caption_list: List[Cap] = Field(default_factory=list)
    font_size: int = Field(default=40, gt=0)
    # 无衬线中文；混剪 Worker 需有对应字库（思源黑体 / Noto Sans CJK 等）
    font_type: str = Field(default="Source Han Sans CN")
    cap_color: str = "#ffffff"
    cap_outline_color: str = "#000000"
    # 混剪 Worker：None 往往等价于无描边；竖屏成片需明显描边以保证白字在亮背景上可读
    cap_outline_width: Optional[float] = Field(ge=0, default=2.0)
    cap_background_color: str = "#000000ff"
    cap_absolute_x: float = Field(ge=0, default=0)
    cap_absolute_y: float = Field(ge=0, default=0.25)
    cap_background_type: int = 0
    cap_line_spacing: int = Field(ge=5, default=10)
    cap_letter_indent: int = Field(ge=0, default=2)

    @field_validator("cap_color", "cap_outline_color")
    @classmethod
    def validate_theme_colors(cls, v: str) -> str:
        if not _is_hex_color(v):
            raise ValueError("cap_color / cap_outline_color 需要形如 #RRGGBB")
        return v
