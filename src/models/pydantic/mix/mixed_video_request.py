from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import Field, model_validator

from models.pydantic.mix.audio_config import AudioConfig
from models.pydantic.mix.base_request import BaseRequest
from models.pydantic.mix.caption_config import CapConfig
from models.pydantic.mix.crop_config import CropConfig
from models.pydantic.mix.filter_config import VideoFilterConfig
from models.pydantic.mix.sticker_config import StickerConfig
from models.pydantic.mix.transition_config import TransitionConfig

Ratio = Literal["1:1", "4:3", "16:9", "3:4", "9:16"]
Resolution = Literal["360p", "720p", "1080p", "2k", "4k"]


class MixedVideoRequest(BaseRequest):
    obs_video_path_list: List[str] = Field(default_factory=list, description="视频链接列表")
    ratio_type: Optional[Ratio] = Field(default=None, description="导出的视频尺幅类型")
    resolution: Optional[Resolution] = Field(default=None, description="导出的视频分辨率")
    fps: int = Field(default=30, ge=20, le=60, description="导出的视频帧率")

    crop_config: List[CropConfig] = Field(default_factory=list, description="裁剪配置")
    cap_config: Optional[CapConfig] = Field(default=None, description="字幕配置")
    local_mode: bool = Field(default=False, description="本地调试模式")

    mute_config: List[bool] = Field(default_factory=list, description="静音设置")
    transition_config: List[Optional[TransitionConfig]] = Field(default_factory=list, description="转场配置")

    obs_audio_path_list: List[str] = Field(default_factory=list, description="音频链接列表")
    audio_config: List[Optional[AudioConfig]] = Field(default_factory=list, description="音频配置")

    filter_config: List[Optional[VideoFilterConfig]] = Field(default_factory=list, description="滤镜配置")

    obs_bgm_path_list: List[str] = Field(default_factory=list, description="背景音乐链接列表")
    bgm_config: List[Optional[AudioConfig]] = Field(default_factory=list, description="背景音乐配置")

    retry_count: Optional[int] = Field(default=0, description="重试次数")
    callback_url: Optional[str] = Field(default=None, description="任务完成后的回调地址")

    sticker_config: List[StickerConfig] = Field(default_factory=list, description="贴纸配置")
    obs_sticker_path_list: Optional[List[str]] = Field(default_factory=list, description="贴纸路径列表")

    request_data: Optional[object] = Field(default=None, description="透传原始请求数据")

    @model_validator(mode="after")
    def validate_business_logic(self) -> MixedVideoRequest:
        num = len(self.obs_video_path_list)

        if num == 0:
            raise ValueError("get empty video path list")

        if self.crop_config and len(self.crop_config) != num:
            raise ValueError(f"传入的裁剪剪辑配置与视频数量{num}不匹配")

        if self.mute_config and len(self.mute_config) != num:
            raise ValueError(f"传入的静音配置与视频数量{num}不匹配")

        if self.transition_config and len(self.transition_config) < num - 1:
            raise ValueError(f"传入的过渡配置数量不足，至少需要{num - 1}个")

        audio_num = len(self.obs_audio_path_list or [])
        audio_cfg_num = len(self.audio_config or [])
        if self.audio_config and audio_num != audio_cfg_num:
            raise ValueError(f"传入的音频配置{audio_cfg_num}和音频数量{audio_num}不匹配")

        if self.filter_config and len(self.filter_config) != num:
            raise ValueError("传入的滤镜配置和视频数量不匹配")

        return self
