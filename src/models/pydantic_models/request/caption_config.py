from pydantic import BaseModel, Field, field_validator
from typing import *

from utils.general_utils import is_valid_hex_color

font_options = [
    "Songti SC Regular",
    "PingFang SC Regular",
    "Alibaba PuHuiTi",
    "DengXian",
    "Heiti TC Medium",
    "Source Han Sans CN",
    "vivo Sans",
    "MiSans",
    "HONOR Sans CN",
    "OPlusSans 3.0",
    "HarmonyOS Sans SC",
    "PangMenZhengDao-Cu6.0",
    "Alibaba Health Font 2.0 CN 85 B",
    "baotuxiaobaiti",
    "SJxingkai-C Regular",
    "YRDZST-Semibold",
    "Slideqiuhong",
    "TsangerShuYuanT W04",
    "QTxiaotu",
    "Noto Color Emoji"
]

class Word(BaseModel):
    start: int = Field(ge=0, alias="from")
    end: int = Field(ge=0, alias="to")
    font_size: Optional[int] = None
    font_type: Optional[Literal[*font_options]] = None
    color: Optional[str] = None
    outline_color: Optional[str] = None
    outline_width: Optional[int] = None

    @field_validator('color', 'outline_color')
    def validate_color(cls, v: str, mode="plain") -> str:
        if v and not is_valid_hex_color(v):
            raise ValueError('字幕颜色需要形如#ffffff格式')
        return v

# 单个字幕内容和时间配置
class Cap(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    cap: str
    rotation: float = Field(default=0)
    absolute_x: Optional[float] = None
    absolute_y: Optional[float] = None
    outline_width: Optional[float] = Field(ge=0, default=None)
    scale: float = Field(default=100, gt=0)
    font_size: Optional[int] = Field(default=30)
    font_type: Literal[*font_options] = None
    color: Optional[str] = None
    outline_color: Optional[str] = None
    background_color: Optional[str] = None
    background_type: int = Field(ge=0, default=0)
    line_spacing: int = Field(ge=0, default=0)
    letter_spacing: int = Field(ge=0, default=0)
    word_config: List[Word] = Field(default_factory=list)

# 字幕样式位置和字幕配置列表
class CapConfig(BaseModel):
    caption_list: List[Cap] = Field(default_factory=lambda: [])
    font_size: int = Field(default=30, gt=0)
    font_type: Literal[*font_options] = "Songti SC Regular"
    cap_color: str = "#ffffff"
    cap_outline_color: str = "#000000"
    cap_outline_width: Optional[float] = Field(ge=0, default=None)
    cap_background_color: str = "#000000ff"
    cap_absolute_x: float = Field(ge=0, default=0)
    cap_absolute_y: float = Field(ge=0, default=0.25)
    cap_background_type: int = 0
    cap_line_spacing: int = Field(ge=5, default=10)
    cap_letter_indent: int = Field(ge=0, default=2)