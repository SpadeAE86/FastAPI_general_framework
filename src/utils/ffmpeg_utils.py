import os, subprocess

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

def split_normalize(video, duration, fade_in=0, fade_out=0):
    dir = os.path.dirname(video)
    vname = os.path.basename(video)
    log.info(f"{vname} fade transition started, fade_in: {fade_in}, fade_out: {fade_out}")
    fade_in_out = '/'.join([dir, f"fade_in_{vname}"]) if fade_in else ''
    middle = '/'.join([dir, f"middle_{vname}"])
    fade_out_out = '/'.join([dir, f"fade_out_{vname}"]) if fade_out else ''

    fade_in_config = [
        "-ss", '0',
        "-to", str(fade_in * 1.2),
        fade_in_out
    ] if fade_in else []

    middle_config = [
        "-ss", str(fade_in * 1.2),
        "-to", f'{duration - fade_out * 1.2}',
        middle
    ]

    fade_out_config = [
        "-ss", f'{duration - fade_out * 1.2}',
        "-to", f'{duration}',
        fade_out_out
    ] if fade_out else []

    ffmpeg_cmd = [
        'ffmpeg',
        '-i', video,
        *fade_in_config,
        *middle_config,
        *fade_out_config,
        "-y"
    ]
    run_ffmpeg_command(ffmpeg_cmd, video_name=vname)

    return fade_in_out, middle, fade_out_out
