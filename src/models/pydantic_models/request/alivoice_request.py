from pydantic import BaseModel
from typing import List, Optional

class Alivoice_VO(BaseModel):
    txt_str: List[str]
    voice_character: str
    audio_speed_level: int
    volume: int
    voice_id: str
    target_speech_rate: Optional[float] = None
    emotion: Optional[str] = None
    intensity: Optional[float] = None

class AliVoiceResponse(BaseModel):
    obs_audio_list: List[str]
    durations: List[float]
    volume: int
    speech_rate: float
    voice_character: str
