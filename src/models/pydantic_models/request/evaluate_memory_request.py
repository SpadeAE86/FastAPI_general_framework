from pydantic import BaseModel, Field
from typing import *

class EvaluateMemoryRequest(BaseModel):
    duration: float = Field(default=30, gt=0, description="导出的总时长")
    fps: float = Field(default=30, gt=0, description="fps")
    resolution_x: float = Field(default=720, ge=360, description="分辨率x" )
    resolution_y: float = Field(default=1280, ge=360, description="分辨率y")