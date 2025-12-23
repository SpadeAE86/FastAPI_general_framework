from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field

class BaseResponse(BaseModel):
    code: int = 0
    message: str = "ok"
