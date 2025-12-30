
import os
from config.config import *
from utils.general_utils import run_ffmpeg_command
from utils.log_utils import logger as log


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


def transition_normalized(videoA, len_A, videoB, len_B, transition_type="fade", transition_duration=1, A_idx=0, B_idx=1,
                          project_id='test'):
    log.info(f"transition transition started, A_len: {len_A}, B_len: {len_B}, type: {transition_type}")
    filter_str = ""
    audio_filter = ""

    output = "/".join([OUTPUT_DIR, project_id, f"transition_{A_idx}_{B_idx}.mp4"])
    d = transition_duration
    s = transition_type
    filter_str += f'[0:v][1:v]xfade=transition={s}:duration={d}:offset={len_A - d}[v01];'
    audio_filter += f"[0:a][1:a]acrossfade=d={d}:c1=exp:c2=exp[a01];"
    vmap_option = ["-map", "[v01]"]
    amap_option = ["-map", "[a01]"]
    vencoder = "h264_nvenc" if my_config['device'] == "gpu" else 'libx264'
    device_option = ['-c:v', vencoder]
    preset_option = ['-preset', 'ultrafast'] if my_config['device'] == "cpu" else []
    filter_str += audio_filter
    gen_transition_command = [
        'ffmpeg',
        '-i', videoA,
        '-i', videoB,
        '-filter_complex', filter_str,
        *vmap_option,
        *amap_option,
        *device_option,
        *preset_option,
        '-movflags', '+faststart',  # 优化播放
        '-pix_fmt', 'yuv420p',
        '-fflags', '+genpts',  # 生成时间戳
        "-y",
        output
    ]
    duration = len_A + len_B - transition_duration
    log.info(f"transition full command: {output}, duration: {duration}")
    run_ffmpeg_command(gen_transition_command, video_name=output)
    return output, duration