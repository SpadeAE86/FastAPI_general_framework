import asyncio
import json
import os
from pydantic.dataclasses import dataclass
from typing import List, Optional

@dataclass
class DynamicRangeInfo:
    type: Optional[str] = None       # SDR / HDR
    hdr_type: Optional[str] = None   # HDR10 / HLG / DolbyVision


@dataclass
class VideoStreamMeta:
    codec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None      # 已归一化（fps / 100）
    bitrate: Optional[int] = None
    dynamic_range: Optional[DynamicRangeInfo] = None


@dataclass
class AudioStreamMeta:
    codec: Optional[str] = None
    sampling_rate: Optional[int] = None
    bitrate: Optional[int] = None


@dataclass
class TranscodeOutput:
    # ===== 输出文件级 =====
    url: Optional[str] = None
    duration: Optional[float] = None          # 秒
    size: Optional[int] = None              # 字节
    width: Optional[int] = None             # 输出分辨率
    height: Optional[int] = None
    # ===== 编码流信息 =====
    video_meta: Optional[VideoStreamMeta] = None
    audio_meta: Optional[AudioStreamMeta] = None
