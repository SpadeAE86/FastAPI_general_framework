from pydantic import BaseModel, Field, model_validator

from typing import *

from models.pydantic_models.request.base_request import BaseRequest

resolution_option = ["720p", "1080p", "2k", "4k"]
# 定义转码请求体
class TranscodeVideoRequest(BaseRequest):

    obs_video_path: str = Field(...,
        description="视频链接"
    )

    transcode_id: Optional[int] = Field(
        default=123,
        description="转码任务 ID"
    )

    target_resolution: Optional[*resolution_option] = Field("1080p", description="目标分辨率")
