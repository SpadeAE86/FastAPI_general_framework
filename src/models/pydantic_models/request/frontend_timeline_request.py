from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.frontend_timeline_response import SpritesData


class FrontendVideoInfo(BaseModel):
    fps: Optional[int] = Field(default=None, description="Optional source fps; used with duration to infer frames")
    duration: Optional[float] = Field(default=None, description="Optional source duration in seconds")
    source_frames: Optional[int] = Field(default=None, description="Optional original source frame count")
    width: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("width", "source_width"),
        serialization_alias="width",
        description="Optional source width",
    )
    height: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("height", "source_height"),
        serialization_alias="height",
        description="Optional source height",
    )
    source_cover: Optional[str] = Field(default=None, description="Optional source cover url")
    material_id: Optional[str] = Field(default=None, description="Optional source material id")
    sprite_cols: int = Field(default=12, description="Default sprite sheet columns")
    sprite_rows: int = Field(default=20, description="Default sprite sheet rows")
    sprite_sample_interval: int = Field(default=5, description="Default sample interval in frames")
    sprite_frame_width: int = Field(default=200, description="Default sprite frame width")
    sprite_frame_height: int = Field(default=112, description="Default sprite frame height")
    sprites: Optional[SpritesData] = Field(
        default=None,
        description="Supplementary sprite sheet metadata; frameCount can be omitted and inferred from duration/fps",
    )


class FrontendAudioInfo(BaseModel):
    voice_character: str = Field(default="小仙(亲切女声)", description="AliVoice voice id")
    audio_speed_level: int = Field(default=0, description="Voice speed level; default falls back to 1.0x")
    volume: int = Field(default=100, description="Volume")
    audio_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("audio_url", "audioUrl"),
        serialization_alias="audio_url",
        description="Optional audio url or obs key for the caption voiceover",
    )
    duration: float = Field(default=3, description="Fallback audio duration in seconds")
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
