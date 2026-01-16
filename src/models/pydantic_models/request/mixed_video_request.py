from pydantic import BaseModel, Field, model_validator

from utils.general_utils import is_valid_hex_color
from .crop_config import CropConfig
from .caption_config import CapConfig, Cap
from .transition_config import TransitionConfig
from .audio_config import AudioConfig
from .filter_config import VideoFilterConfig
from .sticker_config import StickerConfig
from typing import *

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
    }
}
ratio_type_option = ["1:1", "4:3", "16:9", "3:4", "9:16"]
resolution_option = ["720p", "1080p", "2k", "4k"]

# 定义混剪请求体
class MixedVideoRequest(BaseModel):
    obs_video_path_list: List[str] = Field(
        default_factory=list,
        description="视频链接列表"
    )

    ratio_type: Optional[Literal[*ratio_type_option]] = Field(
        default=None,
        description="导出的视频尺幅类型"
    )

    resolution: Optional[Literal[*resolution_option]] = Field(
        default=None,
        description="导出的视频分辨率"
    )

    fps: int = Field(
        default=30,
        ge=20,
        le=60,
        description="导出的视频帧数"
    )

    crop_config: List[CropConfig] = Field(
        default_factory=list,
        description="视频拼接模式配置"
    )

    user_name: str = Field(
        default="",
        description="用户名"
    )

    cap_config: Optional[CapConfig] = Field(
        default=None,
        description="字幕配置"
    )

    local_mode: bool = Field(
        default=False,
        description="本地调试模式"
    )

    mute_config: List[bool] = Field(
        default_factory=list,
        description="静音设置"
    )

    transition_config: List[Optional[TransitionConfig]] = Field(
        default_factory=list,
        description="视频转场配置"
    )

    obs_audio_path_list: List[str] = Field(
        default_factory=list,
        description="音频链接列表"
    )

    audio_config: List[Optional[AudioConfig]] = Field(
        default_factory=list,
        description="音频配置"
    )

    filter_config: List[Optional[VideoFilterConfig]] = Field(
        default_factory=list,
        description="视频调色滤镜配置"
    )

    obs_bgm_path_list: List[str] = Field(
        default_factory=list,
        description="背景音乐链接列表"
    )

    bgm_config: List[Optional[AudioConfig]] = Field(
        default_factory=list,
        description="背景音乐配置"
    )

    mix_id: Optional[int] = Field(
        default=123,
        description="混剪任务 ID"
    )

    trace_id: Optional[int] = Field(
        default=None,
        description="请求链路追踪 ID，用于日志透传与问题排查"
    )

    retry_count: Optional[int] = Field(
        default=0,
        description="重试次数"
    )

    callback_url: Optional[str] = Field(
        default=None,
        description="任务完成后的回调地址"
    )

    sticker_config: List[StickerConfig] = Field(
        default_factory=list,
        description="贴纸配置"
    )

    obs_sticker_path_list: Optional[List[str]] = Field(
        default_factory=list,
        description="贴纸路径列表"
    )

    request_data: Optional[object] = Field(
        default=None,
        description="透传的原始请求数据"
    )

    @model_validator(mode='after')
    def validate_business_logic(self) -> 'MixedVideoRequest':
        num = len(self.obs_video_path_list)

        # 1. 基础非空校验
        if num == 0:
            raise ValueError("get empty video path list")

        if self.crop_config and len(self.crop_config) != num:
            raise ValueError(f"传入的裁剪剪辑配置与视频数量{num}不匹配")

        if self.mute_config and len(self.mute_config) != num:
            raise ValueError(f"传入的静音配置与视频数量{num}不匹配")

        if self.transition_config and len(self.transition_config) < num - 1:
            raise ValueError(f"传入的过渡配置数量不足，至少需要{num - 1}个")

        # 3. 音频匹配校验 (对应原 437)
        audio_num = len(self.obs_audio_path_list or [])
        audio_cfg_num = len(self.audio_config or [])
        if self.audio_config and audio_num != audio_cfg_num:
            raise ValueError(f"传入的音频配置{audio_cfg_num}和音频数量{audio_num}不匹配")

        # 4. 滤镜校验 (对应原 438)
        if self.filter_config and len(self.filter_config) != num:
            raise ValueError("传入的滤镜配置和视频数量不匹配")

        # 5. 颜色合法性校验 (对应原 488)
        if self.cap_config:
            c1 = self.cap_config.get("cap_color")
            c2 = self.cap_config.get("cap_outline_color")
            if not (is_valid_hex_color(c1) and is_valid_hex_color(c2)):
                raise ValueError("输入的颜色不合法, 参考#FFFFFF")

        return self

