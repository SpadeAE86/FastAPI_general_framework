from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

from models.pydantic_models.response.base_response import BaseResponse

class MixedVideoResponse(BaseResponse):
    videoUrl: str
    coverImg: str
    duration: float
    video_size: int
    request_data: Optional[Dict[str, Any]] = None
    isSuccess: bool
    mixId: str