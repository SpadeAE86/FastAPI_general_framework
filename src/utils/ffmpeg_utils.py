import os, subprocess
from dataclasses import dataclass
from typing import Optional

from utils.general_utils import run_ffmpeg_command
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

