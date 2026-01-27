from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

class BaseRequest(BaseModel):
    biz_id: Optional[int] = Field(
        default=0,
        description="业务追踪 ID，用于日志透传与问题排查"
    )

    user_name: str = Field(
        default="user_anonymous",
        description="用户名"
    )

