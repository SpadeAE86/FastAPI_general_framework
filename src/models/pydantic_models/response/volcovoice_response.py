from typing import List, Optional

from pydantic import BaseModel, Field

from models.pydantic_models.response.base_response import BaseResponse


class VolcovoiceDetail(BaseModel):
    segment_url: str = ""
    segment_duration: float = 0.0
    pause: float = 0.0
    caption_text: str = ""


class VolcovoiceObject(BaseModel):
    full_voice: str = ""
    duration: float = 0.0
    detail_info: List[VolcovoiceDetail] = Field(default_factory=list)


class VolcovoiceResponse(BaseResponse):
    object_list: List[VolcovoiceObject] = Field(default_factory=list)
    volume: int
    speech_rate: float
    voice_character: str
    debug_json_url: Optional[str] = None
