from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

from models.pydantic_models.response.base_response import BaseResponse

# 定义混剪响应，url和封面图，文件大小等
class EvaluateMemoryResponse(BaseResponse):
    memory_mb: float = Field(
        description="原始视频内存占用（MB）"
    )