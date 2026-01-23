from typing import Optional, Dict, Any
from models.pydantic_dataclass.transcode_output import TranscodeOutput, AudioStreamMeta, VideoStreamMeta, DynamicRangeInfo
from pydantic import Field

from models.pydantic_models.response.base_response import BaseResponse


# 定义转码请求体
class TranscodeVideoResponse(BaseResponse):
    low_resolution_video_url: str = Field(...,
                                description="转码后低视频链接"
                                )
    low_resolution_video_meta: TranscodeOutput = Field(default_factory=dict,
                                description="转码后低视频信息"
                                )
    raw_resolution_video_url: str = Field(...,
                                description="转码后原视频链接"
                                )
    raw_resolution_video_meta: TranscodeOutput = Field(default_factory=dict,
                                description="转码后低视频信息"
                                )

    transcode_id: Optional[int] = Field(
        default=123,
        description="转码任务 ID"
    )
