from typing import Optional

from pydantic import Field

from models.pydantic_models.response.base_response import BaseResponse


# 定义转码请求体
class TranscodeVideoRequest(BaseResponse):
    low_resolution_video_url: str = Field(...,
                                description="转码后低视频链接"
                                )
    raw_resolution_video_url: str = Field(...,
                                description="转码后原视频链接"
                                )
    raw_resolution_x: int = Field(...,
                        description="转码后高度"
                        )
    raw_resolution_y: int = Field(...,
                    description="转码后宽度"
                    )

    transcode_id: Optional[int] = Field(
        default=123,
        description="转码任务 ID"
    )
