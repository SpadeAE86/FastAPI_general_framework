from pydantic import BaseModel, Field
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
    obs_video_path_list: List[str] = Field(default_factory=lambda: [])  # 视频链接列表
    ratio_type: Literal[*ratio_type_option] = None  # 导出的视频尺幅类型
    resolution: Literal[*resolution_option] = None  # 导出的视频分辨率
    fps: int = Field(default=30, ge=20, le=60)  # 导出的视频帧数
    crop_config: List[CropConfig] = Field(default_factory=lambda: [])  # 视频拼接模式配置
    user_name: str = ""  # 用户名
    cap_config: CapConfig = None  # 字幕配置
    local_mode: bool = Field(default=False)  # 本地调试模式
    mute_config: List[bool] = Field(default_factory=lambda: [])  # 静音设置
    transition_config: List[Optional[TransitionConfig]] = Field(default_factory=lambda: [])  # 视频转场配置
    obs_audio_path_list: List[str] = Field(default_factory=lambda: [])  # 音频链接列表
    audio_config: List[Optional[AudioConfig]] = Field(default_factory=lambda: [])  # 音频配置
    filter_config: List[Optional[VideoFilterConfig]] = Field(default_factory=lambda: [])  # 视频调色滤镜配置
    obs_bgm_path_list: List[str] = Field(default_factory=lambda: [])  # 音频配置
    bgm_config: List[Optional[AudioConfig]] = Field(default_factory=lambda: [])  # 音频配置
    mix_id: Optional[int] = 123
    retry_count: Optional[int] = 0
    callback_url: Optional[str] = None
    sticker_config: List[StickerConfig] = Field(default_factory=lambda: [])  # 贴纸配置
    obs_sticker_path_list: Optional[List[str]] = Field(default_factory=lambda: [])  # 贴纸路径

