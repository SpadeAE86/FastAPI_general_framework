from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

from models.pydantic_models.response.base_response import BaseResponse

# 定义混剪响应，url和封面图，文件大小等
class MixedVideoResponse(BaseResponse):
    videoUrl: str
    coverImg: str
    duration: float
    video_size: int
    request_data: Optional[Dict[str, Any]] = None
    isSuccess: bool
    mixId: str