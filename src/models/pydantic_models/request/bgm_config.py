from pydantic import Field

from .audio_config import AudioConfig


class BgmConfig(AudioConfig):
    ease_in: float = Field(default=0, ge=0, le=5)
    ease_out: float = Field(default=0, ge=0, le=5)
