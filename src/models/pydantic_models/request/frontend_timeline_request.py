from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.frontend_timeline_response import SpritesData

class FrontendTimelineRequest(BaseModel):
    mixed_request: MixedVideoRequest = Field(description='混剪请求')
    fps_list: List[int] = Field(default_factory=list, description='各分镜fps列表')
    sprites_list: List[SpritesData] = Field(default_factory=list, description='雪碧图列表')
