from typing import *

from pydantic import Field, field_validator

from models.pydantic_models.request.base_request import BaseRequest
from utils.obs_utils import obs_key_exists


# 定义雪碧图请求体
class SpriteImageRequest(BaseRequest):

    obs_video_path: str = Field(...,
        description="视频链接"
    )

    @field_validator("obs_video_path")
    @classmethod
    def validate_obs_video_path(cls, v: str) -> str:
        if not obs_key_exists(v):
            raise ValueError("OBS 视频不存在或无访问权限")
        return v