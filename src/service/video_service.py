import concurrent.futures
import os
from functools import partial

from utils.obs_utils import *
from config.config import *
from models.pydantic_models.request.filter_config import FILTER_TEMPLATES

def construct_cache_key(video, crop_config, filter_str, target_w, target_h):
    return f"{video}_{crop_config}_{filter_str}_{target_w}_{target_h}.mp4"

def process_pool_normalize(width, height, fps, video_list, len_list, mixed_video_config, project_id, pix_fmt="yuv420p", cap_helper = None, sticker_list = None,
                           normalize_video_filter_complex=None):
    normalize_process_pool_results = [None] * len(video_list)
    with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
        # 提交所有任务到线程池
        time_so_far = 0
        future_to_idx = {}
        futures = []
        cache_hit_list = []
        filter_str_list = []
        last_cap_idx = -1
        for idx, video_path in enumerate(video_list):
            filter_list = []
            if mixed_video_config.filter_config:
                cfg_list = mixed_video_config.filter_config[idx]
                if cfg_list and cfg_list.filter_template:
                    filter_list.append(FILTER_TEMPLATES[cfg_list.filter_template])
                if cfg_list:
                    for cfg in cfg_list.filter_configs:
                        if cfg.type == "temperature":
                            value = cfg.value / 500 * 1.5
                            filter_list.append(
                                f"colorbalance=rs={value}:rm={value}:rh={value}:bs={-value}:bm={-value}:bh={-value}")
                        elif cfg.type == "brightness":
                            filter_list.append(f"eq=brightness={cfg.value}")
                        elif cfg.type == "tint":
                            value = cfg.value / 500 * 1.5
                            filter_list.append(f"colorbalance=rs={value}:gs={-value}:bs={value}:"
                                               f"rm={value}:gm={-value}:bm={value}:"
                                               f"rh={value}:gh={-value}:bh={value}")
                        elif cfg.type == "contrast":
                            value = cfg.value * 2
                            filter_list.append(f"eq=contrast={value}")
                        elif cfg.type == "saturation":
                            filter_list.append(f"eq=saturation={cfg.value}")
                        elif cfg.type == "hue":
                            filter_list.append(f"hue=h={cfg.value}")
                        elif cfg.type == "sharpness":
                            value = cfg.value * 2
                            filter_list.append(f"unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount={value}")
                        elif cfg.type == "boxblur":
                            filter_list.append(f"boxblur={cfg.value}")
                        elif cfg.type == "gblur":
                            filter_list.append(f"gblur=sigma={cfg.value}")
                        elif cfg.type == "dblur":
                            filter_list.append(f"dblur=angle={cfg.angle}:radius={cfg.value}")

            filter_str = ",".join(filter_list)
            fname = os.path.basename(video_path)
            name, ext = os.path.splitext(fname)
            video = video_path
            start = 0
            end = len_list[idx]
            crop = "full"
            voice_path_list = []
            audio_config = []
            if mixed_video_config.crop_config:
                end = mixed_video_config.crop_config[idx].end
                start = mixed_video_config.crop_config[idx].start
                crop = mixed_video_config.crop_config[idx].model_dump_json(exclude_none=True)
            cache_key = construct_cache_key(name, crop, filter_str, width, height)
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

            if my_config['cache'] and cache_key in memory:
                log.debug(f"cache hit! reuse cache {memory[cache_key]}")
                start = 0
                end = len_list[idx]
                video = memory[cache_key]
                memory.touch(cache_key, video)
                cache_hit = True

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
            cache_hit_list.append(cache_hit)
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
