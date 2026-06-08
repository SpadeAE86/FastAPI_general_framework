from typing import List, Optional, Literal

from pydantic import Field

from models.pydantic_models.request.base_request import BaseRequest
from models.voice_enums import character_options


class Volcovoice_VO(BaseRequest):
    txt_str: List[str]
    voice_character: Literal[*tuple(character_options.keys())]
    file_format: Literal["wav", "mp3"] = Field(default="wav", description="Output audio format for full and segmented files")
    audio_speed_level: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech rate; default is 1.0, range is 0.5 to 2.0")
    volume: int = Field(default=80, ge=0, le=100, description="Voice volume, 0-100")
    target_speech_rate: Optional[float] = None
    emotion: Optional[str] = None
    intensity: Optional[float] = None
