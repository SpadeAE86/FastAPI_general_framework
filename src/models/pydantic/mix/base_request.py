from __future__ import annotations

from pydantic import BaseModel, Field


class BaseRequest(BaseModel):
    biz_id: int = Field(
        ...,
        ge=100,
        le=999,
        description="业务 ID（三位整数 100–999，与测试环境六位 biz_id 区分）；与 mix_video_overall_time、混剪 Worker 对齐",
    )
    user_id: int = Field(default=0, description="用户 ID")
