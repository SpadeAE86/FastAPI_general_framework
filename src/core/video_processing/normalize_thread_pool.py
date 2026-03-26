import concurrent.futures
from functools import partial

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from utils.log_utils import logger as log
from core.video_processing.filter import build_from_config
from core.video_processing.normalize_video import normalize_video_filter_complex


def thread_pool_normalize(
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
        使用线程池并行执行多个视频素材的标准化处理，
        是混剪流程中的「片段调度与并发执行层」。

        本函数会根据 mixed_video_config 中的裁剪、转场、字幕、
        音频、贴纸等配置，为每个视频素材构造对应的
        normalize_video_filter_complex 调用，并通过线程池并行执行。

        函数内部会维护全局时间轴（time_so_far），
        以确保字幕、音频和贴纸在整条视频时间线上的正确对齐。
        所有任务完成后，结果会按原始视频顺序返回。

        Parameters
        ----------
        width : int
            目标输出视频宽度。

        height : int
            目标输出视频高度。

        fps : int or float
            目标输出帧率。

        video_list : list[str]
            视频素材路径列表，顺序即混剪顺序。

        len_list : list[float]
            每个视频片段的时长列表（秒），
            与 video_list 一一对应。

        mixed_video_config : object
            混剪整体配置对象，包含以下子配置（按需使用）：
                - crop_config：裁剪与几何变换配置
                - filter_config：视频滤镜配置
                - cap_config：字幕配置
                - transition_config：转场配置
                - audio_config：音频配置
                - mute_config：静音配置
                - sticker_config：贴纸配置
                - callback_url：AI 混剪模式标志等

        video_info_list : list[VideoInfo]
            每个视频素材的基础信息对象列表，
            与 video_list 一一对应。

        project_id : str
            项目 ID，用于日志、缓存及中间文件区分。

        pix_fmt : str, optional
            输出视频像素格式，如 "yuv420p"。

        cap_helper : object, optional
            字幕图片生成或缓存辅助工具，
            用于减少重复字幕渲染开销。

        sticker_list : list[str], optional
            贴纸资源路径列表。

        audio_path_list : list[str], optional
            口播文件路径列表

        audio_config : list[object], optional
            口播配置列表

        Returns
        -------
        list[NormalizeResult]
            按 video_list 原始顺序返回的标准化处理结果列表。
            每个元素对应一个视频片段，包含：
                - 输出视频路径
                - 实际时长
                - 缓存路径
                - 转场切片信息（SplitClip）

        Notes
        -----
        - 本函数仅负责任务拆分、参数组装与并发调度，
          不直接处理 FFmpeg 细节。
        - 使用 ThreadPoolExecutor，适用于
          I/O 密集型或 FFmpeg 子进程密集型场景。
        - 即使任务完成顺序不同，最终返回结果
          仍会严格保持输入视频顺序。
        - 若任一任务抛出异常，会记录日志，
          但不会影响其他视频的处理流程。
    """

    normalize_results = [None] * len(video_list)

    # ✅ 改为线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        time_so_far = 0
        future_to_idx = {}
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

            future = executor.submit(normalize_func)
            future_to_idx[future] = idx
            futures.append(future)

            time_so_far += len_list[idx]

        # 📊 [可选功能: 进度条状态管理]
        total_duration = sum(len_list) if sum(len_list) > 0 else 1.0
        processed_duration = 0.0
        biz_id = mixed_video_config.biz_id

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
                fidx = future_to_idx.get(future, -1)
                video_path = video_list[fidx] if fidx >= 0 else "unknown"
                log.exception(f"处理失败 {video_path}: {e}")

    return normalize_results