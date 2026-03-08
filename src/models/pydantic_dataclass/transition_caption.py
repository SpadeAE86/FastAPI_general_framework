import asyncio
import json
import os
from pydantic.dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

@dataclass
class CaptionTime:
    caption_path: str = Field(..., description="Path to the caption file.")
    end: float = Field(..., ge=0, description="字幕结束时间")
    start: float = Field(default=0, ge=0, description="字幕开始时间")


@dataclass
class TransitionCaption:
    transition_in_caption_list: List[CaptionTime] = Field(default_factory=list, description="转场渐入字幕")
    transition_out_caption_list: List[CaptionTime] = Field(default_factory=list, description="转场渐出字幕")