from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.frontend_timeline_response import SpritesData


class FrontendVideoInfo(BaseModel):
    fps: Optional[int] = Field(default=None, description="Supplementary fps for frame index and sprites")
    sprites: Optional[SpritesData] = Field(default=None, description="Supplementary sprite sheet metadata")
    source_width: Optional[int] = Field(default=None, description="Optional source width")
    source_height: Optional[int] = Field(default=None, description="Optional source height")
    duration: Optional[float] = Field(default=None, description="Optional source duration in seconds")


class FrontendAudioInfo(BaseModel):
    voice_character: str = Field(default="小仙(亲切女声)", description="AliVoice voice id")
    audio_speed_level: int = Field(default=0, description="Voice speed level; default falls back to 1.0x")
    volume: int = Field(default=100, description="Volume")
    target_speech_rate: Optional[float] = Field(default=None, description="Target speech rate")
    emotion: Optional[str] = Field(default=None, description="Emotion")
    intensity: Optional[float] = Field(default=None, description="Emotion intensity")


class FrontendTimelineRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mix_request: MixedVideoRequest = Field(
        validation_alias=AliasChoices("mix_request", "mixed_request"),
        serialization_alias="mix_request",
        description="Mixed video request",
    )
    video_info_list: List[FrontendVideoInfo] = Field(
        default_factory=list,
        description="Supplementary per-clip video info",
    )
    audio_info_list: Optional[List[FrontendAudioInfo]] = Field(
        default=None,
        description="Optional audio overrides. When missing or null, defaults are used.",
    )
