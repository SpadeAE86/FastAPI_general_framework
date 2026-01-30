import os, subprocess
import time
from dataclasses import dataclass
from typing import Optional

from config.config import FINAL_DIR
from exceptions.ServiceException import ServiceException
from utils.general_utils import run_ffmpeg_command, get_video_info
from utils.log_utils import logger as log


def check_audio_stream_simple(file_path):
    """简化版检查音频流"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a',
            '-show_entries', 'stream=codec_type',
            '-of', 'csv=p=0',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        # 如果输出不为空，则有音频流
        log.info(f"{file_path} has {bool(result.stdout.strip())} audio")
        return bool(result.stdout.strip())
    except subprocess.TimeoutExpired:
        log.error(f"Timeout checking audio stream for {file_path}")
        return False
    except subprocess.CalledProcessError:
        log.info(f"{file_path} has no audio")
        return False

def build_atempo_filter(speed_ratio):
    """
    构建atempo滤镜字符串，处理小于0.5的速度比例
    """
    if speed_ratio >= 0.5:
        return f"atempo={speed_ratio}"

    filters = []
    ratio = speed_ratio
    while ratio < 0.5:
        filters.append("atempo=0.5")
        ratio /= 0.5
    if ratio > 0:
        filters.append(f"atempo={ratio}")

    return ",".join(filters)

@dataclass
class SplitClip:
    main: str
    fade_in: Optional[str] = None
    fade_out: Optional[str] = None

def split_normalize(video, duration, fade_in=0, fade_out=0, transition_reserve_factor = 1.2):
    """
        将已标准化的视频片段按转场需求拆分为多个物理子片段，
        用于后续视频拼接与转场处理。

        根据传入的渐入（fade_in）与渐出（fade_out）时长，
        本函数会在主片段前后预留一定的缓冲区（buffer），
        并将视频切分为以下最多三个部分：
            - 渐入片段（fade_in）
            - 主片段（main）
            - 渐出片段（fade_out）

        为避免转场过程中裁剪不足或特效溢出，
        渐入和渐出片段会按 transition_reserve_factor
        乘以对应的 fade 时长进行扩展切片。

        所有切片操作通过 FFmpeg 执行，并生成独立的视频文件。

        Parameters
        ----------
        video : str
            已完成 normalize 的视频文件路径。

        duration : float
            视频总时长（秒）。

        fade_in : float, optional
            需要用于转场的渐入时长（秒），
            为 0 时不生成渐入片段。

        fade_out : float, optional
            需要用于转场的渐出时长（秒），
            为 0 时不生成渐出片段。

        transition_reserve_factor : float, optional
            转场缓冲系数，用于扩大渐入 / 渐出片段的实际切片时长。
            例如 fade_in=1.0，factor=1.2 时，
            实际切片长度为 1.2 秒。

        Returns
        -------
        SplitClip
            视频拆分结果，包含以下字段：

            - main : str
                主视频片段路径（不包含转场区域）。

            - fade_in : Optional[str]
                渐入视频片段路径，如未指定 fade_in 则为 None。

            - fade_out : Optional[str]
                渐出视频片段路径，如未指定 fade_out 则为 None。

        Notes
        -----
        - 该函数用于「物理切片」，而非 FFmpeg filter 级别的逻辑转场。
        - 生成的 fade_in / fade_out 片段通常会在后续拼接阶段
          与相邻视频进行转场特效处理。
        - 切片文件默认与原视频位于同一目录。
    """
    dir = os.path.dirname(video)
    vname = os.path.basename(video)

    log.info(
        f"{vname} split normalize, "
        f"fade_in={fade_in}, fade_out={fade_out}, "
        f"buffer_factor={transition_reserve_factor}"
    )

    fade_in_path = (
        os.path.join(dir, f"fade_in_{vname}") if fade_in else None
    )
    main_path = os.path.join(dir, f"middle_{vname}")
    fade_out_path = (
        os.path.join(dir, f"fade_out_{vname}") if fade_out else None
    )

    buffer_in = fade_in * transition_reserve_factor
    buffer_out = fade_out * transition_reserve_factor

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", video,
    ]

    if fade_in:
        ffmpeg_cmd += [
            "-ss", "0",
            "-to", str(buffer_in),
            fade_in_path,
        ]

    ffmpeg_cmd += [
        "-ss", str(buffer_in),
        "-to", str(duration - buffer_out),
        main_path,
    ]

    if fade_out:
        ffmpeg_cmd += [
            "-ss", str(duration - buffer_out),
            "-to", str(duration),
            fade_out_path,
        ]

    ffmpeg_cmd.append("-y")

    run_ffmpeg_command(ffmpeg_cmd, video_name=vname)

    return SplitClip(
        main=main_path,
        fade_in=fade_in_path,
        fade_out=fade_out_path,
    )

@dataclass
class SegmentResult:
    """
    I 帧裁切结果：
    - segment: 新生成的视频文件路径
    - start_time / end_time: 在新视频中的相对时间
    """
    segment: str
    start_time: float
    end_time: float

# =========================
# I 帧快速裁切策略（heuristic）
# 使用场景：
# - 用户上传【超长视频】，但只需要其中一小段
# - 直接从原视频精确裁切会导致大量无用解码
# - I 帧分布有时非常稀疏，seek 不准、解码成本高
#
# 核心思路：
# 1. 仅在「视频足够长 && 所需片段相对很小」时启用
# 2. 利用 ffmpeg 的 segment + copy：
#    - 只在 I 帧附近切
#    - 生成更短的视频文件
#    - 后续精确裁切只在短视频上进行
# =========================
def quick_segment(video, vindex, output_dir, start_time, end_time) -> SegmentResult:
    """
    利用 ffmpeg segment + copy 做 I 帧级别的快速裁切

    目标：
    - 避免从视频开头解码到 start_time
    - 只保留「可能包含目标片段」的最小视频范围
    """
    clip_point_list = []
    s = time.time()
    # =========================
    # 计算粗裁切点（10 秒粒度）
    #
    # first_clip:
    #   - 往 start_time 前多留 10 秒
    #   - 防止 I 帧刚好在边界之外
    #
    # second_clip:
    #   - end_time 后多留 20 秒
    #   - 给后续精裁留 buffer
    # =========================
    first_clip = max(10 * (start_time // 10 - 1), 0)
    second_clip = 10 * (2 + end_time // 10)
    log.info(f"first_clip: {first_clip}")
    if first_clip > 0:
        log.info(f"{type(first_clip)},{first_clip > 0} append {first_clip}")
        clip_point_list.append(str(first_clip))
    clip_point_list.append(str(second_clip))
    clip_str = ",".join(clip_point_list)
    segment = video
    # =========================
    # ffmpeg segment 命令说明
    #
    # -ignore_editlist 1
    #   → 忽略 mp4 内部编辑列表，避免时间轴错乱
    #
    # -f segment
    #   → 按时间点切成多个文件
    #
    # -segment_times
    #   → 指定切点（只在 I 帧切）
    #
    # -c copy
    #   → 不重新编码，速度极快
    # =========================
    segment_cmd = [
        'ffmpeg', "-ignore_editlist", "1",
        '-i', video,
        '-f', 'segment',
        '-segment_times', clip_str,
        '-reset_timestamps', '1',
        '-c', 'copy',
        f"{output_dir}segment_{vindex}_%03d.mp4"
    ]
    run_ffmpeg_command(segment_cmd)
    log.info(f"segmented to segment_{vindex}_000.mp4")
    if first_clip == 0:
        # =========================
        # 情况一：first_clip == 0
        # → 说明目标就在视频前部
        # → 直接使用 000 号片段
        # =========================
        segment = f"{output_dir}segment_{vindex}_000.mp4"
        if os.path.exists(f"{output_dir}segment_{vindex}_001.mp4"):
            os.remove(f"{output_dir}segment_{vindex}_001.mp4")
    else:
        # =========================
        # 情况二：first_clip > 0
        # → 生成的 000 是「目标前的视频」
        # → 目标可能在 001 中
        # =========================

        video_info = get_video_info(f"{output_dir}segment_{vindex}_000.mp4")
        w, h, d, r, f, codec = video_info.get_info()
        log.info(f"the duration of before segment_{vindex} is {d}")
        if start_time > d:
            start_time -= d
            end_time -= d
            log.info(f"start_time of segment_{vindex} become {start_time}, end time become {end_time}")
            segment = f"{output_dir}segment_{vindex}_001.mp4"
        if os.path.exists(f"{output_dir}segment_{vindex}_000.mp4"):
            os.remove(f"{output_dir}segment_{vindex}_000.mp4")
        if os.path.exists(f"{output_dir}segment_{vindex}_002.mp4"):
            os.remove(f"{output_dir}segment_{vindex}_002.mp4")
    log.info(f"segment takes {time.time() - s} seconds")

    return SegmentResult(segment=segment,
                         start_time=start_time,
                         end_time=end_time)

def extract_audio(video_file: str, project_id: str = "test") -> str:
    """
    从视频中提取音频（wav），如果没有音频流则返回空字符串
    """

    abs_path = os.path.abspath(video_file)
    fn = os.path.splitext(os.path.basename(video_file))[0]

    output_dir = os.path.join(FINAL_DIR, project_id)
    os.makedirs(output_dir, exist_ok=True)

    output_audio = os.path.join(output_dir, f"{fn}.wav")

    # 1️⃣ 检查是否存在音频流
    check_audio_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        abs_path,
    ]

    try:
        result = subprocess.run(
            check_audio_cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ServiceException(466, "检查是否有音频流失败", data=e.stderr)

    if not result.stdout.strip():
        log.info(f"{video_file} does not contain audio stream")
        return ""

    # 2️⃣ 抽取音频
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", abs_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-f", "wav",
        "-threads", "1",
        output_audio,
        "-y",
    ]

    run_ffmpeg_command(ffmpeg_cmd, video_name=video_file)

    return output_audio

