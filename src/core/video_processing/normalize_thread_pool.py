import concurrent.futures
from functools import partial

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from utils.log_utils import logger as log
from core.video_processing.filter import build_from_config
from core.video_processing.normalize_video import normalize_video_filter_complex


import asyncio
from database.mysql.mysql_manager import db_manager
from models.pydantic_models.db.mix_time_records import MixVideoSceneTime

async def thread_pool_normalize(
    width,
    height,
    fps,
    video_list,
    len_list,
    mixed_video_config: MixedVideoRequest,
    video_info_list,
    project_id,
    pix_fmt="yuv420p",
    cap_helper=None,
    sticker_list=None,
    audio_path_list=None,
    audio_config=None,
):
    """
        (Docstring remains the same, adjusted to an async def function)
    """

    normalize_results = [None] * len(video_list)

    def _time_tracked_normalize(idx, func):
        import time
        t0 = time.time()
        res = func()
        cost = time.time() - t0
        return idx, res, cost

    # ✅ 改为线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        time_so_far = 0
        futures = []

        #从crop_config里取出开始和结束时间
        for idx, video_path in enumerate(video_list):
            filter_str = build_from_config(mixed_video_config.filter_config[idx]) if mixed_video_config.filter_config else ""
            log.info(f"filter str: {filter_str}")
            start = 0
            end = len_list[idx]

            if mixed_video_config.crop_config:
                end = mixed_video_config.crop_config[idx].end
                start = mixed_video_config.crop_config[idx].start

            cache_hit = False
            fade_out_duration = 0
            fade_in_duration = 0


            voice_path_list = audio_path_list

            if idx < len(video_list) - 1 and mixed_video_config.transition_config and mixed_video_config.transition_config[idx]:
                fade_out_duration = mixed_video_config.transition_config[idx].duration
            if idx > 0 and mixed_video_config.transition_config and mixed_video_config.transition_config[idx - 1]:
                fade_in_duration = mixed_video_config.transition_config[idx - 1].duration

            ai_mode = bool(mixed_video_config.callback_url)


            normalize_func = partial(
                normalize_video_filter_complex,
                video_path,  #视频滤镜
                video_info_list[idx],  #视频信息
                end,   #片段结束时间
                width,   #宽度
                height,   #高度
                fps,   #帧率
                mixed_video_config.cap_config,   #字幕配置
                start_time=start,  #片段起始时间
                mute_origin=(   #是否静音
                    mixed_video_config.mute_config
                    and mixed_video_config.mute_config[idx]
                ),
                rotation=mixed_video_config.crop_config[idx].rotation,   #旋转角度
                translate_x=mixed_video_config.crop_config[idx].translate_x,   #水平偏移
                translate_y=mixed_video_config.crop_config[idx].translate_y,   #垂直偏移
                scale=mixed_video_config.crop_config[idx].scale,   #缩放
                mirror=mixed_video_config.crop_config[idx].mirror,   #镜像
                speed=mixed_video_config.crop_config[idx].speed,   #倍速
                extra_filter=filter_str,   #调色滤镜
                project_id=project_id,   #项目id
                processed_so_far=time_so_far,   #分配字幕和音频到各片段时需要额外传入当前视频在整个视频轨道上的时间点
                pix_fmt=pix_fmt,   #像素格式
                cache_hit=cache_hit,   #是否命中缓存，线程池内部变量不共享，只有外部提前判断并传递到内部
                fade_in_duration=fade_in_duration,   #渐入长度
                fade_out_duration=fade_out_duration,   #渐出长度
                audio_config=audio_config,   #音频配置
                audio_path_list=voice_path_list,   #音频路径列表
                vindex=idx,   #是第几个视频
                cap_helper=cap_helper,  #字幕图片helper
                ai_mode=ai_mode,   #是否是ai混剪
                sticker_config=mixed_video_config.sticker_config,   #贴纸配置
                sticker_list=sticker_list,   #贴纸路径列表
            )

            future = executor.submit(_time_tracked_normalize, idx, normalize_func)
            futures.append(future)

            time_so_far += len_list[idx]

        # 📊 [可选功能: 进度条状态管理]
        total_duration = sum(len_list) if sum(len_list) > 0 else 1.0
        processed_duration = 0.0
        biz_id = mixed_video_config.biz_id

        # ✅ 改为 asyncio.as_completed，避免阻塞主线程的 EventLoop
        async_futures = [asyncio.wrap_future(f) for f in futures]
        completed_count = 0
        
        for fut in asyncio.as_completed(async_futures):
            try:
                fidx, result, cost_time = await fut
                normalize_results[fidx] = result
                completed_count += 1

                log.info(
                    f"{video_list[fidx]} 已完成，进度 "
                    f"{completed_count}/{len(video_list)}"
                )
                
                # --- [入库：记录分镜处理时间] ---
                if biz_id:
                    try:
                        async with db_manager.SessionLocal() as session:
                            scene_record = MixVideoSceneTime(
                                biz_id=str(biz_id),
                                scene_idx=fidx,
                                cost_time=round(cost_time, 2)
                            )
                            session.add(scene_record)
                            await session.commit()
                            log.info(f"分镜[{fidx}] 处理时长 {round(cost_time, 2)}s 记录入库成功!")
                    except Exception as db_err:
                        log.warning(f"分镜时间入库失败: {db_err}")

                # --- [可选功能: 更新进度到 Redis] ---
                processed_duration += len_list[fidx]
                if biz_id:
                    try:
                        from celery_mq.task_manager import task_manager
                        from config.config import ENV
                        redis_key = f"{ENV}:{biz_id}_progress"
                        # 留出 1% 给最终合并环节，所以最高记到 0.99
                        current_progress = min(processed_duration / total_duration, 0.99)
                        log.info(f"[normalized threadpool]{biz_id} 目前处理到 {current_progress}({processed_duration}/{total_duration})")
                        # 写进 Redis，设置过期时间为一天(86400秒)防内存泄漏
                        task_manager.redis_client.set(redis_key, str(current_progress), ex=86400)
                    except Exception as progress_err:
                        log.warning(f"更新进度到Redis失败: {progress_err}")
                # ----------------------------------
                
            except Exception as e:
                log.exception(f"处理失败: {e}")

    return normalize_results