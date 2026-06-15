import os
import subprocess
from functools import lru_cache

from config.config import *
from utils.general_utils import random_with_system_time, run_ffmpeg_command
from utils.ffmpeg_utils import build_atempo_filter


@lru_cache(maxsize=128)
def _probe_media_duration(media_path: str) -> float:
    probe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        media_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"failed to probe media duration: {media_path}")
    return float(result.stdout.strip())


def _build_bgm_fade_filters(audio_path: str, cfg, output_duration: float) -> str:
    if not cfg:
        return ""

    start = float(getattr(cfg, "start", 0) or 0)
    end = getattr(cfg, "end", -1)
    offset = float(getattr(cfg, "offset", 0) or 0)
    ease_in = float(getattr(cfg, "ease_in", 0) or 0)
    ease_out = float(getattr(cfg, "ease_out", 0) or 0)
    speed = float(getattr(cfg, "speed", 1.0) or 1.0)

    source_duration = None
    try:
        source_duration = _probe_media_duration(audio_path)
    except Exception:
        pass

    if source_duration is not None:
        source_end = source_duration if end is None or float(end) < 0 else min(float(end), source_duration)
        trimmed_duration = max(source_end - start, 0.0)
    elif end is None or float(end) < 0:
        trimmed_duration = max(output_duration - offset, 0.0) * speed
    else:
        trimmed_duration = max(float(end) - start, 0.0)

    duration_after_speed = trimmed_duration / speed
    visible_duration = min(duration_after_speed, max(output_duration - offset, 0.0))
    if visible_duration <= 0:
        return ""

    actual_fade_in = min(ease_in, visible_duration)
    remaining_after_fade_in = max(visible_duration - actual_fade_in, 0.0)
    actual_fade_out = ease_out if ease_out > 0 and remaining_after_fade_in >= ease_out else 0.0

    fade_parts = []
    if actual_fade_in > 0:
        fade_parts.append(f"afade=t=in:st={offset}:d={actual_fade_in}")
    if actual_fade_out > 0:
        fade_out_start = offset + visible_duration - actual_fade_out
        fade_parts.append(f"afade=t=out:st={fade_out_start}:d={actual_fade_out}")

    return ",".join(fade_parts)


def generate_video(video_path_list, len_list, project_id="test",
                   transition_config=None, audio_path_list=None, audio_config=None, bgm_path_list=None,
                   bgm_config=None, fps=30, bgm_source_path_list=None, bgm_audio_indices=None):
    # 生成视频和音频的代码
    random_name = str(random_with_system_time())
    save_dir = os.path.join(FINAL_DIR, project_id)
    os.makedirs(save_dir, exist_ok=True)
    merge_video = os.path.join(save_dir, "final-" + random_name + ".mp4")

    temp_video_filelist_path = os.path.join(save_dir, 'generate_video_with_audio_file_list.txt')
    temp_video_filelist_path = os.path.abspath(temp_video_filelist_path)

    audio_input = []

    audio_path_list = bgm_path_list
    audio_config = bgm_config
    log.info(f"concat add bgm {audio_path_list} - {audio_config}")
    for a in audio_path_list:
        audio_input += ["-i", a]

    end = sum(len_list)
    if transition_config:
        end -= sum([t.duration for t in transition_config])
    audio_filter = ""
    enda = "0:a"
    audio_simple_filter = []
    if audio_path_list:
        bgm_audio_indices = set(bgm_audio_indices or [])
        weights = ["1"]
        mix_input = ["[main_audio]"]
        audio_filter += f"[{enda}]volume=3[main_audio];"
        enda = "[merged]"
        for idx, a in enumerate(audio_path_list):
            output = f"bgm{idx}"
            crop_offset_str = ""
            source_path = bgm_source_path_list[idx] if bgm_source_path_list and idx < len(bgm_source_path_list) else None
            cfg_audio_url = getattr(audio_config[idx], "audioUrl", None) if audio_config and audio_config[idx] else None
            # 使用传入的 bgm_audio_indices 严格判定是否为纯人声轨（完美适配本地缓存后的 UUID 乱码文件名）
            is_audio_index = idx in bgm_audio_indices
            
            # 为了在 normalize=1 开启时补偿音量衰减并确保绝对不炸麦：
            # - 人声轨使用 18.0 倍率进行增幅，除以3后实得为 6.0（完全还原原 audio_config 时 2.0*3=6.0 的绝佳听感）
            # - BGM 轨使用 6.0 倍率进行增幅，除以3后实得为 2.0 倍的配比量（还原原 BGM 0.3*2=0.6 的听感）
            bgm_volume_multiplier = 18.0 if is_audio_index else 6.0
            volume = bgm_volume_multiplier
            weight = 1
            if audio_config and audio_config[idx]:
                speed = float(getattr(audio_config[idx], "speed", 1.0) or 1.0)
                if audio_config[idx].end >= 0:
                    crop_offset_str += f"atrim=start={audio_config[idx].start}:end={audio_config[idx].end},asetpts=PTS-STARTPTS,"
                else:
                    crop_offset_str += f"atrim=start={audio_config[idx].start},asetpts=PTS-STARTPTS,"
                if speed != 1.0:
                    crop_offset_str += f"{build_atempo_filter(speed)},asetpts=PTS-STARTPTS,"
                if audio_config[idx].offset >= 0:
                    crop_offset_str += f"adelay={audio_config[idx].offset * 1000}|{audio_config[idx].offset * 1000},"
                volume = audio_config[idx].volume * bgm_volume_multiplier
                weight = audio_config[idx].weight
                fade_filter = _build_bgm_fade_filters(a, audio_config[idx], end)
                if fade_filter:
                    crop_offset_str += f"{fade_filter},"
            log.info(
                f"concat bgm idx={idx}, is_audio_index={is_audio_index}, "
                f"volume_multiplier={bgm_volume_multiplier}, volume={volume}, "
                f"weight={weight}, local_path={a}, source_path={source_path}, cfg_audio_url={cfg_audio_url}"
            )
            audio_filter += f"[{1 + idx}:a]{crop_offset_str}volume={volume}[{output}];"
            mix_input.append(f"[{output}]")
            weights.append(str(weight))
        # todo: 根据官方提供的例子 ffmpeg -i VOCALS -i MUSIC -filter_complex amix=inputs=2:duration=longest:dropout_transition=0:weights="1 0.25":normalize=0 OUTPUT
        weight_str = " ".join(weights)

        audio_filter += f'{"".join(mix_input)}amix=inputs={len(audio_path_list) + 1}:duration=longest:weights=\'{weight_str}\':normalize=1,asetpts=N/SR/TB{enda};'
    else:
        audio_simple_filter = ["-af", "asetpts=N/SR/TB"]
    endv = "0:v"
    filter_complex_str = f"{audio_filter}"
    complex_option = ["-filter_complex", filter_complex_str] if filter_complex_str else []
    video_map = ["-map", f"{endv}"]
    audio_map = ["-map", f"{enda}"]
    audio_encoder = ["-c:a", "aac"]
    # 创建包含所有视频文件的文本文件
    with open(temp_video_filelist_path, 'w') as f:
        for video_file in video_path_list:
            abs_path = os.path.abspath(video_file)
            f.write(f"file '{abs_path}'\n")

    log.info(f"时长列表: {len_list}")

    video_encoder = ["-c:v", "copy"]
    threads_option = ["-threads", "1"]
    cover_output = f"./final/{project_id}/cover_test3.jpg"
    cover_cmd = ["-vframes", "1", cover_output]
    # [FIX-CONCAT-STUTTER] 移除 -vsync vfr 和 -fflags +genpts
    # 原因：使用 MKV 中间格式后，每个片段 of PTS 已正确从 0 开始，
    #       不再需要这些 workaround 参数。-vsync vfr 会导致最终视频
    #       r_frame_rate=120 而非预期的 30fps。
    ffmpeg_concat_cmd = ['ffmpeg',
                         '-f', 'concat',
                         '-safe', '0',
                         '-i', temp_video_filelist_path,
                         *audio_input,
                         *complex_option,
                         *audio_simple_filter,
                         '-r', str(fps),  # [FIX] 动态设置拼接后的元数据帧率，防止假元数据导致的解析失败
                         *video_map,
                         *audio_map,
                         *video_encoder,
                         *threads_option,
                         *audio_encoder,
                         '-to', str(float(end)),
                         '-preset', 'fast',
                         '-movflags', '+faststart',
                         '-y',
                         merge_video,
                         *cover_cmd
                         ]

    run_ffmpeg_command(ffmpeg_concat_cmd)
    return merge_video, cover_output
