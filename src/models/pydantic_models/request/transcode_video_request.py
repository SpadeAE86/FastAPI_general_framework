from typing import *

from pydantic import Field

from models.pydantic_models.request.base_request import BaseRequest

Resolution = Literal["720p", "1080p", "2k", "4k"]
# 定义转码请求体
class TranscodeVideoRequest(BaseRequest):

    obs_video_path: str = Field(...,
        description="视频链接"
    )