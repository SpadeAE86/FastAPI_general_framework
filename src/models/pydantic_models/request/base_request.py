from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

class BaseRequest(BaseModel):
    trace_id: Optional[int] = Field(
        default=0,
        description="请求链路追踪 ID，用于日志透传与问题排查"
    )

    user_name: str = Field(
        default="user_anonymous",
        description="用户名"
    )