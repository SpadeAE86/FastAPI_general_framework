from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

from models.pydantic_models.response.base_response import BaseResponse

#
class SpriteImageResponse(BaseResponse):
    coverImg: str
    duration: float
    sprite_id: int = Field(
        default=123,
        description="雪碧图任务 ID"
    )