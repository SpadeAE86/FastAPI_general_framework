import os

from config.config import *
from utils.general_utils import random_with_system_time, run_ffmpeg_command


def generate_video(video_path_list, len_list, project_id="test",
                   transition_config=None, audio_path_list=None, audio_config=None, bgm_path_list=None,
                   bgm_config=None):
    # 生成视频和音频的代码
    random_name = str(random_with_system_time())
    save_dir = os.path.join(FINAL_DIR, project_id)
    os.makedirs(save_dir, exist_ok=True)
    merge_video = os.path.join(save_dir, "final-" + random_name + ".mp4")

    temp_video_filelist_path = os.path.join(save_dir, 'generate_video_with_audio_file_list.txt')
    temp_video_filelist_path = os.path.abspath(temp_video_filelist_path)

    audio_input = []
    if transition_config:
        log.info(f"转场时bgm和voice的传参分开")
        audio_path_list = bgm_path_list
        audio_config = bgm_config
    for a in audio_path_list:
        audio_input += ["-i", a]

    end = sum(len_list)
    if transition_config:
        end -= sum([t.duration for t in transition_config])
    audio_filter = ""
    enda = "0:a"
    if audio_path_list:
        weights = ["1"]
        mix_input = ["[main_audio]"]
        audio_filter += f"[{enda}]volume=3[main_audio];"
        enda = "[merged]"
        for idx, a in enumerate(audio_path_list):
            output = f"bgm{idx}"
            crop_offset_str = ""
            volume = 2
            weight = 1
            if audio_config and audio_config[idx]:
                if audio_config[idx].end >= 0:
                    crop_offset_str += f"atrim=start={audio_config[idx].start}:end={audio_config[idx].end},"
                if audio_config[idx].offset >= 0:
                    crop_offset_str += f"adelay={audio_config[idx].offset * 1000}|{audio_config[idx].offset * 1000},"
                volume = audio_config[idx].volume * 2
                weight = audio_config[idx].weight
            audio_filter += f"[{1 + idx}:a]{crop_offset_str}volume={volume}[{output}];"
            mix_input.append(f"[{output}]")
            weights.append(str(weight))
        # todo: 根据官方提供的例子 ffmpeg -i VOCALS -i MUSIC -filter_complex amix=inputs=2:duration=longest:dropout_transition=0:weights="1 0.25":normalize=0 OUTPUT
        weight_str = " ".join(weights)

        audio_filter += f'{"".join(mix_input)}amix=inputs={len(audio_path_list) + 1}:duration=longest:weights=\'{weight_str}\':normalize=0{enda};'
    endv = "0:v"
    filter_complex_str = f"{audio_filter}"
    complex_option = ["-filter_complex", filter_complex_str] if filter_complex_str else []
    video_map = ["-map", f"{endv}"]
    audio_map = ["-map", f"{enda}"]
    audio_encoder = ["-c:a", "aac"] if audio_path_list else []
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
    ffmpeg_concat_cmd = ['ffmpeg',
                         '-f', 'concat',
                         '-safe', '0',
                         '-i', temp_video_filelist_path,
                         "-vsync", "passthrough",
                         *audio_input,
                         *complex_option,
                         *video_map,
                         *audio_map,
                         *video_encoder,
                         *threads_option,
                         *audio_encoder,
                         '-to', str(float(end)),
                         '-preset', 'fast',
                         '-movflags', '+faststart',
                         '-fflags',
                         '+genpts',
                         '-y',
                         merge_video,
                         *cover_cmd
                         ]
    log.info(f"full command:\n{" ".join(ffmpeg_concat_cmd)}")
    run_ffmpeg_command(ffmpeg_concat_cmd)
    return merge_video, cover_output