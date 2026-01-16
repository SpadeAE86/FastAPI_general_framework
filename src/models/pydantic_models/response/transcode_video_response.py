from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

from models.pydantic_models.response.base_response import BaseResponse


# 定义转码请求体
class TranscodeVideoRequest(BaseResponse):
    obs_video_path: str = Field(...,
                                description="转码后视频链接"
                                )
    height: int = Field(...,
                        description="转码后高度"
                        )
    width: int = Field(...,
                    description="转码后宽度"
                    )

    transcode_id: Optional[int] = Field(
        default=123,
        description="转码任务 ID"
    )
