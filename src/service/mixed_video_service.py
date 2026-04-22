import asyncio
from typing import List

from core.video_processing.generate_video import generate_video
from core.video_processing.normalize_thread_pool import thread_pool_normalize
from core.video_processing.normalize_video import NormalizeResult
from core.transition_video import transition_normalized
from models.pydantic_models.request import audio_config
from models.pydantic_models.response.mixed_video_response import MixedVideoResponse
from utils.general_utils import delete_folder, VideoInfo
from core.video_processing.caption import CapHelper
from exceptions.ServiceException import ServiceException
from utils.general_utils import random_with_system_time, download_resource, get_video_info
from config.config import *
from utils.log_utils import logger as log
import time, json
from datetime import datetime
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest, ratio_option
from asyncio import Semaphore
from utils.obs_utils import upload_to_obs

# --- 数据库依赖 ---
from database.mysql.mysql_manager import db_manager
from models.pydantic_models.db.mix_time_records import MixVideoOverallTime

# 信号量：这个业务逻辑同一时间只能跑一个
semaphore = Semaphore(1)

async def mixed_video_service(mixed_config: MixedVideoRequest):

    project_id = "mix_" + str(random_with_system_time()) if not mixed_config.biz_id else "mix_" + str(
        mixed_config.biz_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")

    # 获取信号量，完成后释放
    async with semaphore:

        current_time = datetime.now()
        log.info(f"{len(mixed_config.obs_video_path_list)}个视频的混剪请求")
        log.info(f"于{current_time}收到请求体")
        log.info(f"{json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
        log.info(f"env: {my_config['env']}")

        log.info(f"config user_id: {mixed_config.user_id}")
        
        # --- [入库：记录混剪开始] ---
        biz_id_str = str(mixed_config.biz_id or project_id)
        
        task_received_dt = None
        if isinstance(mixed_config.request_data, dict):
            raw_time = mixed_config.request_data.get("task_received_at")
            if raw_time:
                try:
                    if isinstance(raw_time, str):
                        task_received_dt = datetime.fromisoformat(raw_time)
                    elif isinstance(raw_time, (int, float)):
                        task_received_dt = datetime.fromtimestamp(raw_time)
                except Exception:
                    pass

        overall_record = MixVideoOverallTime(
            biz_id=biz_id_str,
            status="started",
            start_time=current_time,
            task_received_at=task_received_dt,
            request_data=mixed_config.model_dump_json(exclude_none=True)
        )
        try:
            async with db_manager.SessionLocal() as session:
                session.add(overall_record)
                await session.commit()
                # 刷新以获取自动生成的自增 ID（可选，视需要而定）
                await session.refresh(overall_record)
        except Exception as db_err:
            log.warning(f"记录总体混剪开始状态失败: {db_err}")
            overall_record.id = None
        # -----------------------------

        download_cost = 0; cap_gen_cost = 0; normalize_cost = 0; concat_elapsed = 0; upload_cost = 0
        try:
            download_start = time.time()

            output_dir = None
            # 下载/vpc储存卷获取资源
            if my_config["direct_download"]:
                output_dir = f"{RESOURCE_DIR}/{project_id}"
                os.makedirs(output_dir, exist_ok=True)
            download_task = []
            for p in [mixed_config.obs_video_path_list,
                        mixed_config.obs_audio_path_list,
                        mixed_config.obs_bgm_path_list,
                        mixed_config.obs_sticker_path_list]:
                if p:
                    download_task.append(asyncio.create_task(download_resource(p, output_dir=output_dir)))
                else:
                    download_task.append(asyncio.create_task(asyncio.sleep(0, result=[])))  # 占位任务，保持结果顺序

            video_list, audio_list, bgm_list, sticker_list = await asyncio.gather(*download_task)

            start_1 = time.time()  # 业务开始时间
            log.info(f"download takes {start_1 - download_start} seconds")  # 打印下载时间
            video_list = [os.path.abspath(p) for p in video_list]  # 获取视频全局路径方便后续不同层级的文件引用

            download_cost = start_1 - download_start

            # 创建视频本地路径和源路径的元组列表
            video_info_and_original_path_list = zip(video_list, mixed_config.obs_video_path_list)

            # 获取视频信息
            get_info_task = [asyncio.to_thread(get_video_info, v, need_rotation=True, original_path=origin_v) for v, origin_v in video_info_and_original_path_list]
            video_info_list: List[VideoInfo] = await asyncio.gather(*get_info_task)

            all_video_info = [vinfo.get_info() for vinfo in video_info_list]


            _, _, _, _, pix_format_list, _ = zip(*all_video_info)
            if all([pf == "yuv422p10le" for pf in pix_format_list]):
                pix_fmt = "yuv422p10le"
            elif all([pf == "yuv420p10le" for pf in pix_format_list]):
                pix_fmt = "yuv420p10le"
            else:
                pix_fmt = "yuv420p"

            # 第一个视频的尺幅作为不给出具体分辨率时的兜底
            first_video_info = video_info_list[0]
            width, height, duration, rot, pix_format, codec = first_video_info.get_info()
            log.info(f"first video is {mixed_config.obs_video_path_list[0]} have {rot} rotation")
            # 如果有90度旋转则需要交换横竖尺幅
            if abs(rot) in [90, 270]:
                tmp = width
                width = height
                height = tmp

            if mixed_config.ratio_type and mixed_config.resolution:
                width, height = ratio_option[mixed_config.resolution][mixed_config.ratio_type]

            # 打印最终参考尺幅
            log.info(f"width: {width}")
            log.info(f"height: {height}")
            # 通过crop_config获取时长列表
            len_list = [(c.end - c.start) if c else 0 for c in
                        mixed_config.crop_config] if mixed_config.crop_config else [0] * len(video_list)
            log.info(f"video duration list: {len_list}")

            #生成字幕图片实例，储存生成的图片
            cap_start = time.time()
            cap_helper = None
            if mixed_config.cap_config:
                cap_helper = CapHelper(project_id, width, height, mixed_config.cap_config)
                cap_helper.gen_cap_mapping()
                log.debug(f"subtitle png cap list: {cap_helper.get_cap_list()}")
            cap_gen_cost = time.time() - cap_start

            normalize_start = time.time()

            fps = mixed_config.fps  # 获取fps
            # 线程池调度归一化逻辑
            normalize_thread_pool_results = await thread_pool_normalize(width, height, fps, video_list,
                                                                   len_list, mixed_config, video_info_list ,project_id,
                                                                   pix_fmt=pix_fmt, cap_helper=cap_helper,
                                                                   sticker_list=sticker_list, audio_path_list=audio_list,
                                                                  audio_config=mixed_config.audio_config)

            normalized_results: list[NormalizeResult] = normalize_thread_pool_results
            normalize_cost = time.time() - normalize_start
            log.info(
                f"normalize takes {normalize_cost} in total"
            )

            if not normalized_results or not all(normalized_results):
                log.error(f"error normalize result: {normalized_results}")
                raise ServiceException(577, "error normalize result")
            num = len(normalized_results)
            final_video_list: list[str] = []

            # 处理转场
            if mixed_config.transition_config:
                transition_configs = mixed_config.transition_config

                for idx, result in enumerate(normalized_results):
                    clip = result.transition

                    # 当前 clip 的 transition 配置（最后一个一定没有）
                    transition_cfg = (
                        transition_configs[idx]
                        if idx < len(normalized_results) - 1
                        else None
                    )

                    # 没有 transition：只追加主片段
                    if not transition_cfg:
                        final_video_list.append(clip.main)
                        continue

                    next_clip = normalized_results[idx + 1].transition

                    # 校验 transition 资源
                    if not (clip.fade_out and next_clip.fade_in):
                        raise ServiceException(494, "混剪预处理并没有妥善完成")

                    # 获取 fade 段时长（从 SplitClip 预计算值中获取，无需 ffprobe）
                    dA = clip.fade_out_duration
                    dB = next_clip.fade_in_duration

                    log.info(f"v{idx}_fade_out: {dA}")
                    log.info(f"v{idx + 1}_fade_in: {dB}")
                    log.info(f"v{idx}-{idx + 1} transition: {transition_cfg}")

                    transition_captions = []
                    if clip.transition_caption and clip.transition_caption.transition_out_caption_list:
                        transition_captions.extend(clip.transition_caption.transition_out_caption_list)
                    if next_clip.transition_caption and next_clip.transition_caption.transition_in_caption_list:
                        transition_captions.extend(next_clip.transition_caption.transition_in_caption_list)

                    reserve_A = clip.fade_out_reserve

                    transition_path, _ = transition_normalized(
                        clip.fade_out,
                        dA,
                        next_clip.fade_in,
                        dB,
                        transition_cfg.transition_style,
                        transition_cfg.duration,
                        idx,
                        idx + 1,
                        project_id,
                        transition_captions=transition_captions,
                        reserve_A=reserve_A
                    )

                    # 顺序是：当前 main → transition
                    final_video_list.extend([
                        clip.main,
                        transition_path,
                    ])
            else:
                # 没有任何 transition，直接拼 main
                final_video_list = [
                    r.transition.main for r in normalized_results
                ]

            video_list = list(final_video_list)   # 获取转场后的片段

            # 拼接视频，额外加上bgm
            concat_start = time.time()
            task = asyncio.to_thread(generate_video, video_list, len_list, project_id,
                                     transition_config=mixed_config.transition_config,
                                     audio_path_list=audio_list,
                                     audio_config=mixed_config.audio_config,
                                     bgm_path_list=bgm_list,
                                     bgm_config=mixed_config.bgm_config)

            output_file, cover_img = await task
            concat_elapsed = time.time() - concat_start
            elapsed = time.time() - start_1
            log.info(f"mixed video takes {concat_elapsed} seconds to concat")
            log.info(f"mixed video takes {elapsed} seconds to generate")  #打印总时长
            log.info(f"{output_file}, {cover_img} created successfully!")

            # 获取文件大小
            file_size = os.path.getsize(output_file)  # 单位：字节

            # 上传视频
            upload_start = time.time()
            upload_video_path = f"aigc/aigc_{my_config['env']}/{mixed_config.user_id}/"
            obs_video_url, obs_cover_url = await asyncio.gather(upload_to_obs(output_file, obs_prefix=upload_video_path, project_id=project_id),
                                                                upload_to_obs(cover_img, obs_prefix=upload_video_path, project_id=project_id))
            upload_cost = time.time() - upload_start
            log.info(f"successfully uploaded to obs available by {obs_video_url}")
            log.info(f"upload tasks {upload_cost} 秒")
            log.info(f"[normalized threadpool]{mixed_config.biz_id} 目前处理到100%")
            # 文件回收
            if cap_helper and ENV != "test":
                cap_helper.delete_cap_png()
            # 清空中间文件夹和结果文件夹，本地环境不清理方便调试
            if mixed_config.obs_video_path_list and ENV !="local":
                # asyncio.create_task(delete_folder(os.path.join("./video", project_id)))
                # asyncio.create_task(delete_folder(os.path.join("./work", project_id)))
                asyncio.create_task(delete_folder(os.path.join("./final", project_id)))

            # 计算时长
            if mixed_config.transition_config:
                duration = sum(len_list) - sum([tr.duration if tr else 0 for tr in mixed_config.transition_config])
            else:
                duration = sum(len_list)

            # 计算处理时间
            end_time_dt = datetime.now()
            cost_time = (end_time_dt - current_time).total_seconds()

            # --- [入库：记录混剪结束与总耗时] ---
            if overall_record.id is not None:
                try:
                    async with db_manager.SessionLocal() as session:
                        # 读取最新记录再修改
                        record = await session.get(MixVideoOverallTime, overall_record.id)
                        if record:
                            record.status = "done"
                            record.end_time = end_time_dt
                            record.cost_time = round(cost_time, 2)
                            record.download_cost = round(download_cost, 2)
                            record.cap_gen_cost = round(cap_gen_cost, 2)
                            record.normalize_cost = round(normalize_cost, 2)
                            record.concat_cost = round(concat_elapsed, 2)
                            record.upload_cost = round(upload_cost, 2)

                            record.output_url = obs_video_url
                            record.cover_url = obs_cover_url
                            session.add(record)
                            await session.commit()
                            log.info(f"大盘总体任务耗时入库成功! {record.biz_id} | 耗时: {round(cost_time, 2)}s")
                except Exception as db_err:
                    log.warning(f"更新总体混剪结束状态失败: {db_err}")
            # -----------------------------

            # 构造返回体
            resp = MixedVideoResponse(
                message = f"{num} video being processed",
                video_url= obs_video_url,
                cover_img= obs_cover_url,
                duration= round(duration, 2),
                request_data = mixed_config.request_data,
                video_size = file_size,
                biz_id = mixed_config.biz_id,
                start_time = current_time.strftime("%Y-%m-%d %H:%M:%S"),
                end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S"),
                cost_time = round(cost_time, 2)
            )
            return resp
        except Exception as e:
            end_time_dt = datetime.now()
            cost_time = (end_time_dt - current_time).total_seconds()
            log.error(f"业务处理发生异常: {e}")
            if overall_record.id is not None:
                try:
                    async with db_manager.SessionLocal() as session:
                        record = await session.get(MixVideoOverallTime, overall_record.id)
                        if record:
                            record.status = "failed"
                            record.end_time = end_time_dt
                            record.cost_time = round(cost_time, 2)
                            if "download_cost" in locals() and download_cost: record.download_cost = round(download_cost, 2)
                            if "cap_gen_cost" in locals() and cap_gen_cost: record.cap_gen_cost = round(cap_gen_cost, 2)
                            if "normalize_cost" in locals() and normalize_cost: record.normalize_cost = round(normalize_cost, 2)
                            record.error_msg = str(e)[:500]
                            session.add(record)
                            await session.commit()
                except Exception as db_err:
                    log.warning(f"更新总体混剪失败状态失败: {db_err}")
            raise e
