from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

class BaseResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    biz_id: int = Field(
        default=0,
        description="业务追踪 ID，用于日志透传与问题排查"
    )
