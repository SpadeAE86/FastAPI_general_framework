import concurrent.futures
from functools import partial
from utils.log_utils import logger as log
from core.video_processing.filter import build_from_config
from core.video_processing.normalize_video import normalize_video_filter_complex


def thread_pool_normalize(
    width,
    height,
    fps,
    video_list,
    len_list,
    mixed_video_config,
    video_info_list,
    project_id,
    pix_fmt="yuv420p",
    cap_helper=None,
    sticker_list=None,
):
    normalize_results = [None] * len(video_list)

    # ✅ 改为线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        time_so_far = 0
        future_to_idx = {}
        futures = []

        for idx, video_path in enumerate(video_list):
            filter_str = build_from_config(mixed_video_config.filter_config)
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
                if idx < len(video_list) - 1 and mixed_video_config.transition_config[idx]:
                    fade_out_duration = mixed_video_config.transition_config[idx].duration
                if idx > 0 and mixed_video_config.transition_config[idx - 1]:
                    fade_in_duration = mixed_video_config.transition_config[idx - 1].duration

            ai_mode = bool(mixed_video_config.callback_url)

            normalize_func = partial(
                normalize_video_filter_complex,
                video_path,
                video_info_list[idx],
                end,
                width,
                height,
                fps,
                mixed_video_config.cap_config,
                start_time=start,
                mute_origin=(
                    mixed_video_config.mute_config
                    and mixed_video_config.mute_config[idx]
                ),
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
                fade_in_duration=fade_in_duration,
                fade_out_duration=fade_out_duration,
                audio_config=audio_config,
                audio_path_list=voice_path_list,
                vindex=idx,
                cap_helper=cap_helper,
                ai_mode=ai_mode,
                sticker_config=mixed_video_config.sticker_config,
                sticker_list=sticker_list,
            )

            future = executor.submit(normalize_func)
            future_to_idx[future] = idx
            futures.append(future)

            time_so_far += len_list[idx]

        # ✅ 按完成顺序回收，但结果按 idx 放回
        completed_count = 0
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                fidx = future_to_idx[future]
                normalize_results[fidx] = result
                completed_count += 1

                log.info(
                    f"{video_list[fidx]} 已完成，进度 "
                    f"{completed_count}/{len(video_list)}"
                )
            except Exception as e:
                fidx = future_to_idx.get(future, -1)
                video_path = video_list[fidx] if fidx >= 0 else "unknown"
                log.exception(f"处理失败 {video_path}: {e}")

    return normalize_results