"""
视频处理模块：提供视频标准化、字幕生成等核心处理功能
"""
# 向后兼容：重新导出所有内容
from core.video_processing import normalize_video
from core.video_processing import normalize_process_pool
from core.video_processing import caption

__all__ = [
    'normalize_video',
    'normalize_process_pool',
    'caption',
]

