import concurrent.futures
import os
from functools import partial
from core.filter import build_from_config
from core.normalize_video import normalize_video_filter_complex
from utils.memory_utils import memory
from utils.obs_utils import *
from config.config import *
from models.pydantic_models.request.filter_config import FILTER_TEMPLATES

def construct_cache_key(video, crop_config, filter_str, target_w, target_h):
    return f"{video}_{crop_config}_{filter_str}_{target_w}_{target_h}.mp4"

def process_pool_normalize(width, height, fps, video_list, len_list, mixed_video_config, project_id,
                           pix_fmt="yuv420p", cap_helper = None, sticker_list = None):
    normalize_process_pool_results = [None] * len(video_list)
    with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
        # 提交所有任务到进程池
        time_so_far = 0
        future_to_idx = {}
        futures = []
        cache_hit_list = []
        filter_str_list = []
        last_cap_idx = -1
        for idx, video_path in enumerate(video_list):
            filter_str = build_from_config(mixed_video_config.filter_config)
            fname = os.path.basename(video_path)
            video = video_path
            start = 0
            end = len_list[idx]

            voice_path_list = []
            audio_config = []
            if mixed_video_config.crop_config:
                end = mixed_video_config.crop_config[idx].end
                start = mixed_video_config.crop_config[idx].start
            cache_hit = False
            fade_out_duration = 0
            fade_in_duration = 0

            if mixed_video_config.transition_config:
                voice_path_list = mixed_video_config.obs_audio_path_list
                audio_config = mixed_video_config.audio_config
                if idx < len(video_list)-1 and mixed_video_config.transition_config[idx]:
                    fade_out_duration = mixed_video_config.transition_config[idx].duration
                if idx > 0 and mixed_video_config.transition_config[idx-1]:
                    fade_in_duration = mixed_video_config.transition_config[idx-1].duration

            cap_cnt = mixed_video_config.crop_config[idx].cap_cnt
            # 把所有参数都放到partial里，包括video_path
            ai_mode = bool(mixed_video_config.callback_url)
            normalize_func = partial(
                normalize_video_filter_complex,
                video,  # 第一个位置参数
                end,  # 第二个位置参数
                width,  # 第三个位置参数
                height,  # 第四个位置参数
                fps,  # 第五个位置参数
                mixed_video_config.cap_config,  # 第六个位置参数
                # 命名参数
                last_cap_idx = last_cap_idx,
                cap_cnt = cap_cnt,
                start_time=start,
                mute_origin=mixed_video_config.mute_config and mixed_video_config.mute_config[idx],
                rotation=mixed_video_config.crop_config[idx].rotation,
                translate_x=mixed_video_config.crop_config[idx].translate_x,
                translate_y=mixed_video_config.crop_config[idx].translate_y,
                scale=mixed_video_config.crop_config[idx].scale,
                mirror=mixed_video_config.crop_config[idx].mirror,
                speed=mixed_video_config.crop_config[idx].speed,
                extra_filter=filter_str,
                project_id=project_id,
                processed_so_far=time_so_far,
                pix_fmt=pix_fmt,
                cache_hit=cache_hit,
                fade_in_duration = fade_in_duration,
                fade_out_duration = fade_out_duration,
                audio_config = audio_config,
                audio_path_list = voice_path_list,
                vindex = idx,
                cap_helper = cap_helper,
                ai_mode = ai_mode,
                sticker_config = mixed_video_config.sticker_config,
                sticker_list = sticker_list
            )

            future = executor.submit(normalize_func)
            future_to_idx[future] = idx
            futures.append(future)
            filter_str_list.append(filter_str)
            time_so_far += len_list[idx]
            last_cap_idx += cap_cnt


        # 实时获取完成的任务，不等批次完成
        completed_count = 0
        for idx, future in enumerate(concurrent.futures.as_completed(futures)):
            try:
                result = future.result()
                fidx = future_to_idx[future]
                normalize_process_pool_results[fidx] = result
                video_path = video_list[fidx]
                vname = os.path.basename(video_path)
                name, ext = os.path.splitext(vname)
                crop = mixed_video_config.crop_config[fidx]
                filter_str = filter_str_list[fidx]
                cache_key = construct_cache_key(name, crop.model_dump_json(exclude_none=True), filter_str, width,
                                                height)
                if not cache_hit_list[fidx]:
                    memory[cache_key] = result[2]
                completed_count += 1

                log.info(f"{video_path}已完成: {result}, 当前进度: {completed_count}/{len(video_list)}")
            except Exception as e:

                log.info(f"处理失败 {video_path}: {e}")
        return normalize_process_pool_results
