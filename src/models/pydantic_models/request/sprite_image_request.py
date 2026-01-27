from typing import *

from pydantic import Field

from models.pydantic_models.request.base_request import BaseRequest


# 定义雪碧图请求体
class SpriteImageRequest(BaseRequest):

    obs_video_path: str = Field(...,
        description="视频链接"
    )


