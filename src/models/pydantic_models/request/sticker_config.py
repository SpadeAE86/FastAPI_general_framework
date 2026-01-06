from pydantic import BaseModel, Field
from typing import *

class StickerConfig(BaseModel):
    start: float = Field(ge=0, default=0, description = "绝对的起始时间")
    end: float = Field(default=-1, description = "绝对的结束时间")
    scale: float = Field(default=1.0, gt=0)