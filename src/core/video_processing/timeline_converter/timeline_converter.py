from dataclasses import dataclass
from typing import Optional, Tuple

from utils.log_utils import logger as log


@dataclass(frozen=True)
class TimelineConverter:
    """
    全局时间轴 → 当前片段局部时间轴 的统一换算器。

    所有时间参数均为 speed 后的值（speed 已在上游处理）。

    Attributes
    ----------
    processed_so_far : float
        当前片段在全局（输出）时间轴上的起始位置（秒）。
    clip_duration : float
        当前片段在输出时间轴上的时长（秒），已受 speed 影响。
    start_time : float
        ffmpeg -ss 的起始偏移（秒），已受 speed 影响。
    """
    processed_so_far: float
    clip_duration: float
    start_time: float = 0.0

    # ── 属性 ────────────────────────────────────────────────
    @property
    def global_end(self) -> float:
        """当前片段在全局时间轴上的结束位置"""
        return self.processed_so_far + self.clip_duration

    # ── 字幕类映射 ──────────────────────────────────────────
    def map_start_end(
            self,
            global_start: float,
            global_end: float,
    ) -> Optional[Tuple[float, float]]:
        """
        将全局 (start, end) 区间映射为当前片段的局部时间区间。

        Parameters
        ----------
        global_start : float
            全局时间轴上的起始时间。
        global_end : float
            全局时间轴上的结束时间。

        Returns
        -------
        Optional[Tuple[float, float]]
            (local_start, local_end)，裁剪到 [0, clip_duration]。
            若完全不在当前片段范围内，返回 None。
        """
        # 完全在当前片段之前
        if global_end <= self.processed_so_far:
            return None
        # 完全在当前片段之后
        if global_start >= self.global_end:
            return None

        local_start = max(global_start - self.processed_so_far, 0.0)
        local_end = global_end - self.processed_so_far
        # 裁剪到片段时长范围内
        local_end = min(local_end, self.clip_duration)

        log.debug(
            f"map_start_end: global({global_start:.3f}, {global_end:.3f}) "
            f"-> local({local_start:.3f}, {local_end:.3f}) "
            f"[psf={self.processed_so_far:.3f}, dur={self.clip_duration:.3f}]"
        )
        return local_start, local_end

    # ── offset 类映射 ─────────────────────────────────────────
    def map_offset_range(
            self,
            global_offset: float,
            src_start: float = 0.0,
            src_end: float = -1.0,
    ) -> Optional[Tuple[float, float, float]]:
        """
        将全局 offset + 裁剪区间映射为当前片段的局部参数。

        offset 表示某资源在全局时间轴上的播放起始点；
        src_start / src_end 是该资源自身的裁剪范围（透传）。

        Parameters
        ----------
        global_offset : float
            资源在全局时间轴上的起始位置（秒）。
        src_start : float
            资源自身裁剪的起始时间（秒），透传。
        src_end : float
            资源自身裁剪的结束时间（秒），透传。-1 表示不裁剪。

        Returns
        -------
        Optional[Tuple[float, float, float]]
            (local_offset, src_start, src_end)
            - local_offset: 资源在当前片段中的延迟（秒）
            - src_start: 透传的裁剪起始
            - src_end: 透传的裁剪结束
            若 offset 不在当前片段范围内，返回 None。
        """
        local_offset = global_offset - self.processed_so_far

        # 起始点超出当前片段时长
        if local_offset >= self.clip_duration:
            log.debug(
                f"map_offset_range: offset {global_offset:.3f} "
                f"beyond clip end {self.global_end:.3f}, skip"
            )
            return None

        # 起始点在当前片段之前
        if local_offset < 0:
            # 判断该音频是否能在当前片段播放（即其结束时间是否晚于当前片段起始时间）
            if src_end < 0:
                global_end = float('inf')
            elif src_end > global_offset:
                # 传入的是全局结束时间
                global_end = src_end
            else:
                # 传入的是资源自身裁剪区间结束值（本地相对时间）
                global_end = global_offset + (src_end - src_start)

            if global_end <= self.processed_so_far:
                log.debug(
                    f"map_offset_range: offset {global_offset:.3f} and end {global_end:.3f} "
                    f"before clip start {self.processed_so_far:.3f}, skip"
                )
                return None

            # 计算在当前片段需要裁剪跳过的时长
            skip_duration = self.processed_so_far - global_offset
            src_start = src_start + skip_duration
            local_offset = 0.0

            log.debug(
                f"map_offset_range: overlap offset {global_offset:.3f} "
                f"-> local {local_offset:.3f}s, skipped {skip_duration:.3f}s, new src_start {src_start:.3f} "
                f"[psf={self.processed_so_far:.3f}, dur={self.clip_duration:.3f}]"
            )
            return local_offset, src_start, src_end

        log.debug(
            f"map_offset_range: offset {global_offset:.3f} "
            f"-> local {local_offset:.3f}s "
            f"[psf={self.processed_so_far:.3f}, dur={self.clip_duration:.3f}]"
        )
        return local_offset, src_start, src_end
