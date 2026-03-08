from typing import *

from pydantic import Field, field_validator

from models.pydantic_models.request.base_request import BaseRequest
from utils.obs_utils import obs_key_exists

Resolution = Literal["720p", "1080p", "2k", "4k"]
# 定义转码请求体
class TranscodeVideoRequest(BaseRequest):

    obs_video_path: str = Field(...,
        description="视频链接"
    )

    @field_validator("obs_video_path")
    @classmethod
    def validate_obs_video_path(cls, v: str) -> str:
        if not obs_key_exists(v):
            raise ValueError("OBS 视频不存在或无访问权限")
        return v