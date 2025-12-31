import os, subprocess
import time
from dataclasses import dataclass
from typing import Optional

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
    segment: str
    start_time: float
    end_time: float

def quick_segment(video, vindex, output_dir, start_time, end_time) -> SegmentResult:
    clip_point_list = []
    s = time.time()
    first_clip = max(10 * (start_time // 10 - 1), 0)
    second_clip = 10 * (2 + end_time // 10)
    log.info(f"first_clip: {first_clip}")
    if first_clip > 0:
        log.info(f"{type(first_clip)},{first_clip > 0} append {first_clip}")
        clip_point_list.append(str(first_clip))
    clip_point_list.append(str(second_clip))
    clip_str = ",".join(clip_point_list)
    segment = video
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
        segment = f"{output_dir}segment_{vindex}_000.mp4"
        if os.path.exists(f"{output_dir}segment_{vindex}_001.mp4"):
            os.remove(f"{output_dir}segment_{vindex}_001.mp4")
    else:
        w, h, d, r, f = get_video_info(f"{output_dir}segment_{vindex}_000.mp4")
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