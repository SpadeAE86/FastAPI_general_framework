from typing import Literal, Optional

from pydantic import Field, model_validator

from utils.general_utils import is_valid_hex_color
from .audio_config import AudioConfig
from .bgm_config import BgmConfig
from .base_request import BaseRequest
from .caption_config import CapConfig
from .crop_config import CropConfig
from .filter_config import VideoFilterConfig
from .sticker_config import StickerConfig
from .transition_config import TransitionConfig


ratio_option = {
    "720p": {
        "1:1": (720, 720),
        "4:3": (960, 720),
        "16:9": (1280, 720),
        "3:4": (720, 960),
        "9:16": (720, 1280),
    },
    "1080p": {
        "1:1": (1080, 1080),
        "4:3": (1440, 1080),
        "16:9": (1920, 1080),
        "3:4": (1080, 1440),
        "9:16": (1080, 1920),
    },
    "2k": {
        "1:1": (1440, 1440),
        "4:3": (1920, 1440),
        "16:9": (2560, 1440),
        "3:4": (1440, 1920),
        "9:16": (1440, 2560),
    },
    "4k": {
        "1:1": (2160, 2160),
        "4:3": (2880, 2160),
        "16:9": (3840, 2160),
        "3:4": (2160, 2880),
        "9:16": (2160, 3840),
    },
}

Ratio = Literal["1:1", "4:3", "16:9", "3:4", "9:16"]
Resolution = Literal["360p", "720p", "1080p", "2k", "4k"]


class MixedVideoRequest(BaseRequest):
    obs_video_path_list: list[str] = Field(default_factory=list, description="Video path list")
    ratio_type: Optional[Ratio] = Field(default=None, description="Output aspect ratio")
    resolution: Optional[Resolution] = Field(default=None, description="Output resolution")
    fps: int = Field(default=30, ge=20, le=60, description="Output fps")
    crop_config: list[CropConfig] = Field(default_factory=list, description="Per-clip crop config")
    cap_config: Optional[CapConfig] = Field(default=None, description="Caption config")
    local_mode: bool = Field(default=False, description="Local debug mode")
    mute_config: list[bool] = Field(default_factory=list, description="Mute config")
    transition_config: list[Optional[TransitionConfig]] = Field(default_factory=list, description="Transition config")
    obs_audio_path_list: list[str] = Field(default_factory=list, description="Voiceover audio path list")
    audio_config: list[Optional[AudioConfig]] = Field(default_factory=list, description="Voiceover audio config")
    filter_config: list[Optional[VideoFilterConfig]] = Field(default_factory=list, description="Filter config")
    obs_bgm_path_list: list[str] = Field(default_factory=list, description="BGM path list")
    bgm_config: list[Optional[BgmConfig]] = Field(default_factory=list, description="BGM config")
    retry_count: Optional[int] = Field(default=0, description="Retry count")
    callback_url: Optional[str] = Field(default=None, description="Callback url")
    sticker_config: list[StickerConfig] = Field(default_factory=list, description="Sticker config")
    obs_sticker_path_list: Optional[list[str]] = Field(default_factory=list, description="Sticker path list")
    request_data: Optional[object] = Field(default=None, description="Raw request payload")

    @model_validator(mode="after")
    def validate_business_logic(self) -> "MixedVideoRequest":
        num = len(self.obs_video_path_list)
        if num == 0:
            raise ValueError("get empty video path list")

        if self.crop_config and len(self.crop_config) != num:
            raise ValueError(f"crop_config count {len(self.crop_config)} does not match video count {num}")

        if self.mute_config and len(self.mute_config) != num:
            raise ValueError(f"mute_config count {len(self.mute_config)} does not match video count {num}")

        if self.transition_config and len(self.transition_config) < num - 1:
            raise ValueError(f"transition_config count must be at least {num - 1}")

        audio_num = len(self.obs_audio_path_list or [])
        audio_cfg_num = len(self.audio_config or [])
        if self.audio_config and audio_num != audio_cfg_num:
            raise ValueError(f"audio_config count {audio_cfg_num} does not match audio path count {audio_num}")

        bgm_num = len(self.obs_bgm_path_list or [])
        bgm_cfg_num = len(self.bgm_config or [])
        if self.bgm_config and bgm_num != bgm_cfg_num:
            raise ValueError(f"bgm_config count {bgm_cfg_num} does not match bgm path count {bgm_num}")

        if self.filter_config and len(self.filter_config) != num:
            raise ValueError("filter_config count does not match video count")

        if self.cap_config:
            c1 = self.cap_config.cap_color
            c2 = self.cap_config.cap_outline_color
            if not (is_valid_hex_color(c1) and is_valid_hex_color(c2)):
                raise ValueError("invalid caption colors, expected hex values like #FFFFFF")

        return self
