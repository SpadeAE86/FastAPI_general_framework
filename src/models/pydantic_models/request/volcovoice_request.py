from typing import List, Optional, Literal

from pydantic import Field

from models.pydantic_models.request.base_request import BaseRequest
from models.voice_enums import character_options


class Volcovoice_VO(BaseRequest):
    txt_str: List[str]
    voice_character: Literal[*tuple(character_options.keys())]
    audio_speed_level: int = Field(default=0, description="Speech rate level; 0 means the default speed")
    volume: int = Field(default=80, ge=0, le=100, description="Voice volume, 0-100")
    target_speech_rate: Optional[float] = None
    emotion: Optional[str] = None
    intensity: Optional[float] = None
