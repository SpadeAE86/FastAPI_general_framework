from pydantic import BaseModel
from typing import List, Optional
from models.pydantic_models.request.base_request import BaseRequest

class Alivoice_VO(BaseRequest):
    txt_str: List[str]
    voice_character: str
    audio_speed_level: int
    volume: int
    target_speech_rate: Optional[float] = None
    emotion: Optional[str] = None
    intensity: Optional[float] = None
