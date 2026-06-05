import math
from dataclasses import dataclass

from config.config import *
from core.video_processing.caption import CaptionDistributor
from exceptions.ServiceException import ServiceException
from models.pydantic_models.request import transition_config
from models.pydantic_models.request.caption_config import CapConfig
from utils.ffmpeg_utils import check_audio_stream_simple, build_atempo_filter, split_normalize, SplitClip, \
    quick_segment, SegmentResult
from utils.general_utils import run_ffmpeg_command, VideoInfo
from core.video_processing.timeline_converter import TimelineConverter


@dataclass
class NormalizeResult:
    output: str                 # output_name
    duration: float
    transition: SplitClip

def normalize_video_filter_complex(video, video_info: VideoInfo, end_time, width, height, fps, cap_config: CapConfig,
                                   start_time=0, mute_origin=False,
                                   project_id='test', translate_x=0, translate_y=0, rotation=0, scale=1,
                                   mirror=False, speed=1, extra_filter="", processed_so_far=0, pix_fmt="yuv420p",
                                   cache_hit=False, fade_in_duration=0, fade_out_duration=0, audio_config=None,
                                   audio_path_list=None, vindex = 0, cap_helper = None, ai_mode = False,
                                   sticker_config = None, sticker_list= None, freeze_tail_duration=0):
    """
    对单个视频素材进行标准化处理并生成 FFmpeg filter_complex，
    用于视频混剪流水线中的「单片段处理阶段」。

    该函数会根据传入的裁剪、变换、字幕、贴纸、音频等配置，
    对原始素材视频进行如下处理（按需启用）：
        - 时间裁剪 / 倍速
        - 分辨率统一、像素格式转换
        - 平移 / 旋转 / 缩放 / 镜像
        - 颜色或自定义滤镜（extra_filter）
        - 渐入 / 渐出
        - 原音频静音或重配音频
        - 字幕图片与贴纸叠加
    最终输出可直接拼接到整体混剪的 FFmpeg filter_complex 中。

    该函数通常通过 functools.partial 预绑定参数，
    交由线程池 / 进程池并行执行。

    Parameters
    ----------
    video : str
        视频素材文件路径。

    video_info : VideoInfo
        视频基础信息对象，包含分辨率、时长、编码格式等元数据。

    end_time : float
        当前片段允许的最大时长（秒），通常为片段结束时间。

    width : int
        目标输出视频宽度。

    height : int
        目标输出视频高度。

    fps : int or float
        目标输出帧率。

    cap_config : CapConfig
        字幕配置对象，用于控制字幕内容、样式与出现时机。

    start_time : float, optional
        当前片段在原视频中的起始时间（秒）。

    mute_origin : bool, optional
        是否静音原始视频音频。

    project_id : str, optional
        项目 ID，用于日志、缓存或中间产物区分。

    translate_x : int or float, optional
        视频在 X 轴方向的平移偏移量。

    translate_y : int or float, optional
        视频在 Y 轴方向的平移偏移量。

    rotation : int or float, optional
        视频旋转角度（度）。

    scale : float, optional
        视频缩放比例。

    mirror : bool, optional
        是否进行水平镜像翻转。

    speed : float, optional
        视频播放倍速（>1 加速，<1 减速）。

    extra_filter : str, optional
        额外的 FFmpeg 视频滤镜字符串（如调色、风格化滤镜）。

    processed_so_far : float, optional
        当前片段在整条视频时间轴上的起始时间（秒），
        用于字幕、音频在全局时间轴上的对齐。

    pix_fmt : str, optional
        输出视频像素格式，如 "yuv420p"。

    cache_hit : bool, optional
        是否命中缓存结果。
        由于线程池内状态不共享，需要由外部判断并传入。

    fade_in_duration : float, optional
        视频渐入时长（秒）。

    fade_out_duration : float, optional
        视频渐出时长（秒）。

    audio_config : object, optional
        音频处理配置，如配音、音量、对齐方式等。

    audio_path_list : list[str], optional
        可用的音频文件路径列表（配音 / BGM 等）。

    vindex : int, optional
        当前视频在混剪序列中的索引位置。

    cap_helper : object, optional
        字幕图片或缓存辅助工具，用于减少重复生成字幕资源。

    ai_mode : bool, optional
        是否为 AI 混剪模式，用于切换特定处理逻辑。

    sticker_config : object, optional
        贴纸相关配置（出现时间、位置、层级等）。

    sticker_list : list[str], optional
        贴纸资源路径列表。

    Returns
    -------
    NormalizeResult
        单个视频片段的处理结果，包含以下字段：

        - output : str
            当前片段生成的视频文件名（或输出标识）。

        - duration : float
            实际生成片段的视频时长（秒）。

        - cache_path : str
            缓存文件路径，用于后续复用或跳过重复处理。

        - transition : SplitClip
            转场相关片段信息，用于后续拼接处理，其中：
                - main : str
                    主视频片段路径。
                - fade_in : Optional[str]
                    渐入视频片段路径（如存在）。
                - fade_out : Optional[str]
                    渐出视频片段路径（如存在）。
    """

    # 获取视频信息
    fname = os.path.basename(video)
    name, ext = os.path.splitext(fname)
    video_width, video_height, source_duration, rot, pix_format, codec = video_info.get_info()
    # 旋转90度交换视频长宽
    if abs(rot) in [90, 270]:
        video_width, video_height = video_height, video_width
    log.info(f"start normalize {video} with :, {video_width}, {video_height}, |target:, {width}, {height}")


    # 创建文件夹
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    subfolder = "/".join([OUTPUT_DIR, project_id])
    os.makedirs(subfolder, exist_ok=True)

    output_prefix = os.path.join(subfolder, f"normalized_{start_time}_{end_time}_")
    output_name = output_prefix + str(vindex) + "_" + fname

    if start_time > source_duration:
        raise ServiceException(code=439, message=f"{video}起始时间{start_time}大于视频时长{source_duration}")
    end_time = min(source_duration, end_time)  #主动校准结束点，不会超过视频结束时间

    muted_audio = []
    translate_x = translate_x * video_width
    translate_y = -translate_y * video_height



    # 通过I帧快速切分文件（由于I帧分布有的时候非常疏松，所以只裁切时长30秒以上并所需片段不到总时长1/5的视频，并且裁切范围）
    segment = video
    segment_to_remove = []
    if source_duration > 30 and source_duration / (end_time - start_time) >= 5:

        segment_dir = f"{OUTPUT_DIR}/{project_id}/"
        os.makedirs(f"{segment_dir}", exist_ok=True)
        log.info(f"{end_time - start_time}/{source_duration} >=5, make extra cropping ")  #huristic
        segment_result: SegmentResult = quick_segment(segment, vindex, segment_dir, start_time, end_time)  #快速裁切
        segment = segment_result.segment
        segment_to_remove.append(segment)
        start_time = segment_result.start_time
        end_time = segment_result.end_time

    end_v= "[0:v]"  #如果没滤镜就直接

    video_filter_list = []   # 总滤镜列表
    # 先行滤镜
    pre_transform = []
    raw_start_time = start_time
    raw_end_time = end_time
    pre_transform.append(f"trim=start={raw_start_time}:end={raw_end_time},setpts=PTS-STARTPTS")
    # === GPU → CPU（必须最前）===
    if my_config["device"] == "gpu":
        pre_transform.extend([
            "hwdownload",
            "format=nv12",  # 或 nv12 → yuv420p，CPU 滤镜最稳
        ])

    # === 处理 rotation（只在 CPU 上做）===
    if rot:
        # rot 是 metadata 的角度（90 / 180 / 270）
        # FFmpeg rotate 用的是弧度
        pre_transform.append(
            f"rotate={rot}*PI/180:fillcolor=black"
        )
    pre_transform_str = ",".join(pre_transform)
    if pre_transform_str:
        video_filter_list.append(f"{end_v}{pre_transform_str}[v_pre]")
        end_v = "[v_pre]"



    # 变换滤镜
    preset_option = ['-preset', 'ultrafast'] if my_config['device'] == "cpu" else ['-preset', '12']
    gpu_encoder = []
    if my_config["device"] == "gpu":
        gpu_encoder.extend(["-c:v", "h264_nvenc"])



    # pix_fmt_option = ["-pix_fmt", "nv12"]
    has_audio = check_audio_stream_simple(video)
    # 音频静音
    if mute_origin or not has_audio:
        log.info(f"video {video} does not have audio stream")
        muted_audio = ["-f", "lavfi", "-i", 'anullsrc=channel_layout=stereo:sample_rate=44100']


    # transform = [
    #     f"scale=-1:{height}:flags=bicubic" if video_width / video_height > width / height else f"scale={width}:-1:flags=bicubic",
    #     f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2"
    # ]
    transform = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
    ]
    audio_filter_str = ""
    # 调色滤镜
    if extra_filter:
        transform.append(f"{extra_filter}")
    # 画面倍速滤镜
    if speed != 1.0:
        transform.append(f"setpts={1.0 / speed}*(PTS-STARTPTS)")
        if not mute_origin:
            audio_filter_str = build_atempo_filter(speed)

    audio_filter_flag = []
    if audio_filter_str and not mute_origin:
        audio_filter_flag = ["-af", audio_filter_str]

    # 镜像滤镜
    if mirror:
        transform.append(f"hflip")
    # 放大缩小滤镜
    if scale != 1:
        if scale < 1:
            transform.append(f"scale=iw*{scale}:ih*{scale}:flags=lanczos")
            transform.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black")
        else:
            # 放大视频，极寒优化：先裁剪出需要保留的中心区域，再缩放回目标画布，避免生成极其恐怖的 8K 甚至 16K 过渡画布！
            crop_w = width / scale
            crop_h = height / scale
            c_x = (width - crop_w) / 2
            c_y = (height - crop_h) / 2
            transform.append(f"crop={crop_w}:{crop_h}:{c_x}:{c_y}")
            transform.append(f"scale={width}:{height}:flags=lanczos")
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

    # 此时start_time在后续滤镜链中都需要用到提速后的，包括duration时长也会改变
    start_time = float(start_time/speed)
    end_time = float(end_time/speed)
    duration = end_time - start_time
    freeze_tail_duration = float(freeze_tail_duration / speed) if freeze_tail_duration else 0.0
    if abs(freeze_tail_duration) < 1e-6:
        freeze_tail_duration = 0.0
    effective_duration = duration + freeze_tail_duration
    log.info(
        f"normalize durations: source_duration={source_duration}, clip_duration={duration}, "
        f"freeze_tail_duration={freeze_tail_duration}, effective_duration={effective_duration}"
    )
    if duration > 0:
        video_filter_list.append(f"{end_v}trim=start=0:end={duration},setpts=PTS-STARTPTS[trim_v]")
        end_v = "[trim_v]"
    if freeze_tail_duration > 0:
        video_filter_list.append(f"{end_v}tpad=stop_mode=clone:stop_duration={freeze_tail_duration}[freeze_v]")
        end_v = "[freeze_v]"
    converter = TimelineConverter(processed_so_far, effective_duration, start_time)



    # 字幕滤镜
    vf_text = ""
    subtitle_png_input = []
    subtitle_list = []
    transition_caption = None
    if cap_helper:
        caption_distributor = CaptionDistributor(width, height, cap_config, transition_config, cap_helper, project_id)
        subtitle_list, transition_caption = caption_distributor.gen_subtitle_png(
            processed_so_far=processed_so_far,
            duration=effective_duration,
            transition_in=fade_in_duration,
            transition_out=fade_out_duration,
        )

        if sticker_config and sticker_list:
            log.info(f"sticker task=-=")

        cur_stream = f"{end_v}"
        for idx, subtitle_config in enumerate(subtitle_list):
            p = subtitle_config["path"]
            cap_start = subtitle_config["start"]
            cap_end = subtitle_config["end"]
            subtitle_png_input.extend(["-i", p])
            vf_text += f"[{1 + idx}:v]format=rgba,setpts=PTS-STARTPTS[sub{idx}];"
            vf_text += f"{cur_stream}[sub{idx}]overlay=enable='between(t,{cap_start},{cap_end - 0.005})'"
            end_label = f"overlay{idx}"
            cur_stream = f"[{end_label}]"
            if idx == len(subtitle_list) - 1:
                vf_text += f",format=nv12[cap_v]"
            else:
                vf_text += f"{cur_stream};"
        # log.info(f"{vindex} video get caption {subtitle_list}, output to {output_name}")

    # 组装字幕滤镜链并添加到video_filter滤镜
    if vf_text:
        cap_filter = vf_text
    else:
        cap_filter = f"{end_v}null[cap_v]"
    if cap_filter:
        video_filter_list.append(cap_filter)
        end_v = "[cap_v]"

    # 音频滤镜
    raw_audio_label = "0:a" if not mute_origin and has_audio else f"{len(subtitle_list)+1}:a"
    if not mute_origin and has_audio:
        video_filter_list.append(
            f"[{raw_audio_label}]atrim=start={raw_start_time}:end={raw_end_time},asetpts=PTS-STARTPTS[trimmed_a]"
        )
        end_a = "trimmed_a"
    else:
        end_a = raw_audio_label
    weights = ["1.0"]
    audio_input = []
    audio_filter = ""
    audio_simple_filter = []
    if audio_config:
        mix_input = [f"[main_audio]"]
        speed_audio_str = f",{audio_filter_str}" if audio_filter_str else ""
        audio_filter += f"[{end_a}]volume=3{speed_audio_str},atrim=start=0:end={duration},asetpts=PTS-STARTPTS,apad=whole_dur={effective_duration}[main_audio];"
        audio_filter_flag = []  # FFmpeg forbids combining simple (-af) and complex filtergraphs for the same mapped stream
        end_a = "[merged]"
        supplement_audio_input_base = len(subtitle_list) + 1 + int(mute_origin or not has_audio)
        supplement_audio_input_cursor = supplement_audio_input_base

        for idx, a in enumerate(audio_path_list):
            log.info(f"{idx} audio with offset {audio_config[idx].offset}, start={audio_config[idx].start}, end={audio_config[idx].end}, process_so_far={processed_so_far}")
            output = f"bgm{idx}"
            crop_offset_str = ""

            mapped = converter.map_offset_range(
                audio_config[idx].offset,
                audio_config[idx].start,
                audio_config[idx].end,
            )
            if mapped is None:
                continue
            local_offset, src_start, src_end = mapped
            local_delay_ms = local_offset * 1000

            audio_input.append(a)
            if src_end >= 0:
                crop_offset_str += f"atrim=start={src_start}:end={src_end},"
            crop_offset_str += f"adelay={local_delay_ms}|{local_delay_ms},"
            volume = audio_config[idx].volume * 2
            weight = audio_config[idx].weight
            audio_stream_index = supplement_audio_input_cursor
            audio_filter += f"[{audio_stream_index}:a]{crop_offset_str}apad=whole_dur={effective_duration},volume={volume}[{output}];"
            mix_input.append(f"[{output}]")
            weights.append(str(weight))
            supplement_audio_input_cursor += 1
        # todo: 根据官方提供的例子 ffmpeg -i VOCALS -i MUSIC -filter_complex amix=inputs=2:duration=longest:dropout_transition=0:weights="1 0.25":normalize=0 OUTPUT
        weight_str = " ".join(weights)
        audio_filter += f'{"".join(mix_input)}amix=inputs={len(mix_input)}:duration=longest:weights="{weight_str}":normalize=0{end_a}'
    # 组装音频滤镜并添加到video_filter_list
    audio_input_option = []
    for p in audio_input:
        audio_input_option.extend(["-i", p])
    if audio_filter:
        video_filter_list.append(audio_filter)
    else:
        simple_audio_filters = []
        if audio_filter_str:
            simple_audio_filters.append(audio_filter_str)
        simple_audio_filters.append(f"atrim=start=0:end={duration},asetpts=N/SR/TB,apad=whole_dur={effective_duration}")
        audio_simple_filter = ["-af", ",".join(simple_audio_filters)]
        audio_filter_flag = []

    # === 新增配置：统一时基 ===
    # 15360 是一个通用的时基 (90000也是常用的，但15360对mp4很友好)
    # 这确保所有切片的时间“刻度”完全一致，concat copy 时不会错乱
    timebase_option = ["-video_track_timescale", "15360"]

    # === 新增配置：强制常量帧率 (CFR) ===
    # 使用较新的 -fps_mode cfr 替代旧的 -vsync 1
    # 强制补帧或丢帧以严格匹配 -r，防止 nvenc 输出 VFR 导致帧率元数据错误
    cfr_option = ["-fps_mode", "cfr"]

    #后置滤镜上传到gpu
    post_filter = []
    if my_config["device"] == "gpu":
        post_filter.extend(
            [
            "setpts=PTS-STARTPTS",  # [FIX-CONCAT-STUTTER] 强制将送入硬件编码器的时间戳归零，消除 nvenc 首帧 skip frame 卡顿
            "format=nv12",
            "hwupload=derive_device=cuda"
            ]
        )

    post_filter_str = ",".join(post_filter)
    if post_filter_str:
        video_filter_list.append(f"{end_v}{post_filter_str}[v_post]")
        end_v = "[v_post]"


    # 组装总滤镜
    video_filter = ";".join(video_filter_list)

    # 如果不是奇怪的格式，就试用gpu解码
    gpu_cuda_device_init = ["-init_hw_device", "cuda=cuda0"] if my_config['device'] == "gpu" else []
    gpu_activate_flag = ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]\
        if my_config['device'] == "gpu" else []

    # 使用三个filter一次性完成
    normalize_cmd = [
        'ffmpeg', "-ignore_editlist", "1",
        *gpu_cuda_device_init,
        *gpu_activate_flag,
        '-noautorotate',
        '-fflags', '+genpts',
        '-i', segment,
        *subtitle_png_input,
        *muted_audio,
        *audio_input_option,
        *cfr_option,  # <--- 插入统一常量帧率
        '-r', str(fps),
        *gpu_encoder,
        "-threads", "2",
        *preset_option,
        "-filter_complex", video_filter,
        *audio_simple_filter,
        *audio_filter_flag,
        '-ar', '44100',
        '-ac', '2',
        *timebase_option,  # <--- 插入统一时基参数
        '-y',
        '-avoid_negative_ts', 'make_zero',
        '-map', end_v, '-map', f"[{end_a}]" if ":" not in end_a and not end_a.startswith("[") else end_a,
        '-shortest',
        output_name
    ]

    # ffmpeg进程启动
    run_ffmpeg_command(normalize_cmd, video_name=fname)
    log.info(f"{video} 完成处理")

    # 转场分割
    new_length = effective_duration
    if fade_in_duration or fade_out_duration:
        transition_clip = split_normalize(
            output_name,
            new_length,
            fade_in_duration,
            fade_out_duration,
        )
        transition_clip.transition_caption = transition_caption
    else:
        # 没有 transition：整个视频就是 main
        transition_clip = SplitClip(main=output_name)

    # 把多出来的中间文件进行清理，本地不清理方便调试
    if ENV != "local":
        for s in segment_to_remove:
            if os.path.exists(s):
                log.info(f"remove {s}")
                os.remove(s)

    # 组装返回体
    return NormalizeResult(
        output=output_name,
        duration=new_length,
        transition=transition_clip,
    )

