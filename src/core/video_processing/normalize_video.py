import math
from dataclasses import dataclass

from config.config import *
from core.video_processing.caption import CaptionDistributor
from exceptions.ServiceException import ServiceException
from models.pydantic_models.request import transition_config
from utils.ffmpeg_utils import check_audio_stream_simple, build_atempo_filter, split_normalize, SplitClip, quick_segment
from utils.general_utils import run_ffmpeg_command, VideoInfo


@dataclass
class NormalizeResult:
    output: str                 # output_name
    duration: float
    cache_path: str
    transition: SplitClip

def normalize_video_filter_complex(video, video_info: VideoInfo, max_len, width, height, fps, cap_config,
                                   start_time=0, mute_origin=False,
                                   project_id='test', translate_x=0, translate_y=0, rotation=0, scale=1,
                                   mirror=False, speed=1, extra_filter="", processed_so_far=0, pix_fmt="yuv420p",
                                   cache_hit=False, fade_in_duration=0, fade_out_duration=0, audio_config=None,
                                   audio_path_list=None, vindex = 0, cap_helper = None, ai_mode = False,
                                   sticker_config = None, sticker_list= None):

    # 获取视频信息
    fname = os.path.basename(video)
    name, ext = os.path.splitext(fname)
    video_width, video_height, duration, rot, pix_format, codec = video_info.get_info()
    # 旋转90度交换视频长宽
    if abs(rot) in [90, 270]:
        video_width, video_height = video_height, video_width
    print(f"start normalize {video} with :", video_width, video_height, "|target:", width, height)

    # 创建文件夹
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    subfolder = "/".join([OUTPUT_DIR, project_id])
    os.makedirs(subfolder, exist_ok=True)

    # 给缓存命中的情况留口子
    output_prefix = os.path.join(subfolder, f"normalized_{start_time}_{max_len}_")
    output_name = output_prefix + str(vindex) + "_" + fname
    base_name = os.path.join(subfolder, "normalized_" + name)
    if cache_hit:
        # 命中缓存，直接用缓存路径
        output_name = base_name + ".mp4"
    # 如果出现起始时间比结束时间晚，视为异常，未来可以挪到最外层做校验
    if start_time > duration:
        raise ServiceException(code=439, message=f"{video}起始时间{start_time}大于视频时长{duration}")
    max_len = min(duration, max_len)

    muted_audio = []
    translate_x = translate_x * video_width
    translate_y = -translate_y * video_height

    # 缓存文件路径
    cache_video_key = f'{name}_{start_time}_{max_len}.mp4'
    cache_video_path = f"./work/{project_id}/nocap_{vindex}_{cache_video_key}"


    # 通过I帧快速切分文件（由于I帧分布有的时候非常疏松，所以只裁切时长30秒以上并所需片段不到总时长1/5的视频，并且裁切范围）
    segment = video
    segment_to_remove = []
    if duration>30 and duration / (max_len - start_time) >= 5:

        segment_dir = f"{RESOURCE_DIR}/{project_id}/"
        os.makedirs(f"{segment_dir}", exist_ok=True)
        log.info(f"{max_len - start_time}/{duration} >=5, make extra cropping ")  #huristic
        segment_result = quick_segment(segment, vindex, segment_dir, start_time, max_len)
        segment = segment_result.segment
        start_time = segment_result.start_time
        max_len = segment_result.end_time

    end_v= "[0:v]"  #如果没滤镜就直接
    video_filter_list = []   # 总滤镜列表

    # 变换滤镜
    preset_option = ['-preset', 'ultrafast'] if my_config['device'] == "cpu" else ['-preset', '12']
    gpu_encoder = []
    if my_config["device"] == "gpu":
        gpu_encoder.extend(["-c:v", "h264_nvenc"])
    pix_fmt_option = ["-pix_fmt", pix_fmt] if "10le" in pix_format or codec == "mjpeg" else []
    has_audio = check_audio_stream_simple(video)
    # 音频静音
    if mute_origin or not has_audio:
        log.info(f"video {video} does not have audio stream")
        muted_audio = ["-f", "lavfi", "-i", 'anullsrc=channel_layout=stereo:sample_rate=44100']
    audio_filter = ""



    #如果配置是cpu，旋转是90度，10le特殊格式，编码格式是mjpeg等奇怪格式，就用cpu滤镜
    if my_config["device"] == "cpu" or rot != 0 or "10le" in pix_format or codec == "mjpeg":
        # transform = [
        #     f"scale=-1:{height}:flags=bicubic" if video_width / video_height > width / height else f"scale={width}:-1:flags=bicubic",
        #     f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2"
        # ]
        transform = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        ]
    else:
        transform = [
            f"scale_cuda={width}:-1" if video_width / video_height > width / height else f"scale_cuda=-1:{height}",
            f"pad_cuda={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        ]
    # 调色滤镜
    if extra_filter:
        transform.append(f"{extra_filter}")
    # 画面倍速滤镜
    if speed != 1.0:
        transform.append(f"setpts={1.0 / speed}*(PTS-STARTPTS)")
        if not mute_origin:
            audio_filter = ["-af", build_atempo_filter(speed)]
    else:
        if ai_mode and cap_config and cap_config.caption_list[vindex]:
            video_duration = min(max_len, duration) - start_time
            audio_info = cap_config.caption_list[vindex]
            audio_duration = audio_info.end - audio_info.start
            speed =  video_duration / audio_duration
            log.info(f"video_duration: {video_duration}, audio_duration: {audio_duration}")
            if abs(audio_duration-video_duration) > 0.01:
                log.info(f"make speed adjustment on {vindex} video to {speed}, where video_duration become {video_duration / speed}")

                transform.append(f"setpts={1.0 / speed}*(PTS-STARTPTS)")
                if not mute_origin:
                    audio_filter = ["-af", build_atempo_filter(speed)]
    # 镜像滤镜
    if mirror:
        transform.append(f"hflip")
    # 放大滤镜
    if scale != 1:
        transform.append(f"scale=iw*{scale}:ih*{scale}:flags=lanczos")
        if scale < 1:
            transform.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black")
        else:
            # 放大视频，需要crop裁剪掉超出部分（保持原始尺寸）
            transform.append(f"crop={width}:{height}:(iw-ow)/2:(ih-oh)/2")
    # 位移滤镜
    if translate_x or translate_y:
        translate_x = int(translate_x)
        translate_y = int(translate_y)
        log.info(f"translate_x: {translate_x}, translate_y: {translate_y}")
        transform.append(
            f"crop={max(width - abs(translate_x), 2)}:{max(height - abs(translate_y), 2)}:{min(max(-translate_x, 0), width)}:{min(max(translate_y, 0), height)}")
        transform.append(f"pad={width}:{height}:{max(translate_x, 0)}:{max(-translate_y, 0)}:color=black")
    # 旋转滤镜
    if rotation:
        transform.append(f"rotate={rotation * math.pi / 180}:fillcolor=black")
    # 组装变换滤镜链并加入video_filter_list
    transform_str = ",".join(transform)
    if transform_str:
        video_filter_list.append(f"{end_v}{transform_str}[no_cap_v]")
        end_v = "[no_cap_v]"

    # 字幕滤镜
    vf_text = ""
    subtitle_png_input = []
    subtitle_list = []
    if cap_helper:
        log.info(f"cap_outline: {cap_config.cap_outline_width}")
        caption_distributor = CaptionDistributor(width, height, cap_config, transition_config, cap_helper, project_id)
        subtitle_list = caption_distributor.gen_subtitle_png()

        if sticker_config and sticker_list:
            log.info(f"sticker task=-=")

        cur_stream = f"{end_v}"
        for idx, subtitle_config in enumerate(subtitle_list):
            p = subtitle_config["path"]
            start = subtitle_config["start"]
            end = subtitle_config["end"]
            subtitle_png_input.extend(["-i", p])
            vf_text += f"[{1 + idx}:v]format=rgba,setpts=PTS-STARTPTS[sub{idx}];"
            vf_text += f"{cur_stream}[sub{idx}]overlay=enable='between(t,{start + float(start_time/speed)},{end + float(start_time/speed) - 0.005})'"
            end_label = f"overlay{idx}"
            cur_stream = f"[{end_label}]"
            if idx == len(subtitle_list) - 1:
                vf_text += f"[cap_v]"
            else:
                vf_text += f"{cur_stream};"
        log.info(f"{vindex} video get caption {subtitle_list}, output to {output_name}")

    # 组装字幕滤镜链并添加到video_filter滤镜
    if vf_text:
        cap_filter = vf_text
    else:
        cap_filter = f"{end_v}null[cap_v]"
    if cap_filter:
        video_filter_list.append(cap_filter)
        end_v = "[cap_v]"

    # 音频滤镜
    end_a = "0:a" if not mute_origin and has_audio else f"{len(subtitle_list)+1}:a"
    weights = []
    audio_input = []

    if audio_config:
        mix_input = [f"[main_audio]"]
        audio_filter += f"[{end_a}]volume=3[main_audio];"
        end_a = "[merged]"
        cur = len(subtitle_png_input) + 1
        for idx, a in enumerate(audio_path_list):
            output = f"bgm{idx}"
            crop_offset_str = ""
            dur = audio_config[idx].end - audio_config[idx].start
            if audio_config[idx].offset - processed_so_far < 0:
                continue
            audio_input.append(a)
            if audio_config[idx].end >= 0:
                crop_offset_str += f"atrim=start={audio_config[idx].start}:end={audio_config[idx].end},"
            crop_offset_str += f"adelay={(audio_config[idx].offset - processed_so_far) * 1000}|{(audio_config[idx].offset - processed_so_far) * 1000}"
            volume = audio_config[idx].volume * 2
            weight = audio_config[idx].weight
            audio_filter += f"[{1 + cur}:a]{crop_offset_str}apad=whole_dur={max_len},volume={volume}[{output}];"
            mix_input.append(f"[{output}]")
            weights.append(str(weight))
            processed_so_far += dur
            cur += 1
        # todo: 根据官方提供的例子 ffmpeg -i VOCALS -i MUSIC -filter_complex amix=inputs=2:duration=longest:dropout_transition=0:weights="1 0.25":normalize=0 OUTPUT
        weight_str = " ".join(weights)
        audio_filter += f'{"".join(mix_input)}amix=inputs={len(audio_path_list) + 1}:duration=longest:weights="{weight_str}":normalize=0{end_a}'
    # 组装音频滤镜并添加到video_filter_list
    audio_input_option = []
    for p in audio_input:
        audio_input_option.extend(["-i", p])
    if audio_filter:
        video_filter_list.append(audio_filter)
    # 组装总滤镜
    video_filter = ";".join(video_filter_list)
    gpu_activate_flag = ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"] if my_config[
                                                                                      'device'] == "gpu" and "10le" not in pix_format and abs(
        rot) == 0 and codec != "mjpeg" else []
    # 使用三个filter一次性完成
    normalize_cmd = [
        'ffmpeg', "-ignore_editlist", "1",
        *gpu_activate_flag,
        '-i', segment,
        *subtitle_png_input,
        *muted_audio,
        *audio_input_option,
        '-ss', str(float(start_time/speed)), '-to', str(min(max_len, duration)/speed),
        '-r', str(fps),
        *gpu_encoder,
        "-threads", "2",
        *preset_option,
        "-filter_complex", video_filter,
        *audio_filter,
        *pix_fmt_option,
        '-y',
        '-fflags', '+genpts',
        '-map', end_v, '-map', end_a,
        '-shortest',
        output_name
    ]

    run_ffmpeg_command(normalize_cmd, video_name=fname)
    log.info(f"{video} 完成处理")

    # 转场分割
    new_length = min(max_len - start_time, duration) / speed
    if fade_in_duration or fade_out_duration:
        transition_clip = split_normalize(
            output_name,
            new_length,
            fade_in_duration,
            fade_out_duration,
        )
    else:
        # 没有 transition：整个视频就是 main
        transition_clip = SplitClip(main=output_name)

    # 把多出来的中间文件进行清理
    for s in segment_to_remove:
        if os.path.exists(s):
            log.info(f"remove {s}")
            os.remove(s)

    # 组装返回体
    return NormalizeResult(
        output=output_name,
        duration=new_length,
        cache_path=cache_video_path,
        transition=transition_clip,
    )

