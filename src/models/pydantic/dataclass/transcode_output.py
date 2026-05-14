from __future__ import annotations

from typing import Optional

from pydantic.dataclasses import dataclass


@dataclass
class DynamicRangeInfo:
    type: Optional[str] = None
    hdr_type: Optional[str] = None


@dataclass
class VideoStreamMeta:
    codec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    dynamic_range: Optional[DynamicRangeInfo] = None


@dataclass
class AudioStreamMeta:
    codec: Optional[str] = None
    sampling_rate: Optional[int] = None
    bitrate: Optional[int] = None


@dataclass
class TranscodeOutput:
    url: Optional[str] = None
    duration: Optional[float] = None
    size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    video_meta: Optional[VideoStreamMeta] = None
    audio_meta: Optional[AudioStreamMeta] = None
