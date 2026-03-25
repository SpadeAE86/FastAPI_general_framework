from pydantic import BaseModel
from typing import List
from models.pydantic_models.response.base_response import BaseResponse

class AliVoiceResponse(BaseResponse):
    obs_audio_list: List[str]
    durations: List[float]
    volume: int
    speech_rate: float
    voice_character: str
