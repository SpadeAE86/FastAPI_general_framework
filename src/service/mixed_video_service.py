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
        download_start = time.time()

        output_dir = None
        # 下载/vpc储存卷获取资源
        if my_config["direct_download"]:
            output_dir = f"{RESOURCE_DIR}/{project_id}"
            os.makedirs(output_dir, exist_ok=True)
        video_list = await download_resource(mixed_config.obs_video_path_list, output_dir=output_dir)
        audio_list = await download_resource(mixed_config.obs_audio_path_list, output_dir=output_dir)
        bgm_list = await download_resource(mixed_config.obs_bgm_path_list, output_dir=output_dir)
        sticker_list = await download_resource(mixed_config.obs_sticker_path_list, output_dir=output_dir)


        start_1 = time.time()  # 业务开始时间
        log.info(f"download takes {start_1 - download_start} seconds")  # 打印下载时间
        video_list = [os.path.abspath(p) for p in video_list]  # 获取视频全局路径方便后续不同层级的文件引用
        # 获取视频信息
        get_info_task = [asyncio.to_thread(get_video_info, v, need_rotation=True) for v in video_list]
        video_info_list: List[VideoInfo] = await asyncio.gather(*get_info_task)

        all_video_info = [vinfo.get_info() for vinfo in video_info_list]


        _, _, _, _, pix_format_list, _ = zip(*all_video_info)
        if all([pf == "yuv422p10le" for pf in pix_format_list]):
            pix_fmt = "yuv422p10le"
        elif all([pf == "yuv422p10le" for pf in pix_format_list]):
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
        normalize_start = time.time()
        cap_helper = None
        if mixed_config.cap_config:
            cap_helper = CapHelper(project_id, width, height, mixed_config.cap_config)
            cap_helper.gen_cap_mapping()
            log.debug(f"subtitle png cap list: {cap_helper.get_cap_list()}")

        fps = mixed_config.fps  # 获取fps
        # 线程池调度归一化逻辑
        normalize_thread_pool_results = thread_pool_normalize(width, height, fps, video_list,
                                                               len_list, mixed_config, video_info_list ,project_id,
                                                               pix_fmt=pix_fmt, cap_helper=cap_helper,
                                                               sticker_list=sticker_list, audio_path_list=audio_list,
                                                              audio_config=audio_config)

        normalized_results: list[NormalizeResult] = normalize_thread_pool_results
        log.info(
            f"normalize takes {time.time() - normalize_start} in total"
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

                # 获取 fade 段时长
                _, _, dA, _, _, _ = get_video_info(clip.fade_out).get_info()
                _, _, dB, _, _, _ = get_video_info(next_clip.fade_in).get_info()

                log.info(f"v{idx}_fade_out: {dA}")
                log.info(f"v{idx + 1}_fade_in: {dB}")
                log.info(f"v{idx}-{idx + 1} transition: {transition_cfg}")

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

        # 拼接视频，额外加上声音和bgm
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
        log.info(f"successfully uploaded to obs available by {obs_video_url}")
        log.info(f"upload tasks {time.time() - upload_start} 秒")

        # 文件回收
        if cap_helper:
            cap_helper.delete_cap_png()
        # 清空中间文件夹和结果文件夹
        if mixed_config.obs_video_path_list:
            pass
            # asyncio.create_task(delete_folder(os.path.join("./video", project_id)))
            # asyncio.create_task(delete_folder(os.path.join("./work", project_id)))
            # asyncio.create_task(delete_folder(os.path.join("./final", project_id)))

        # 计算时长
        if mixed_config.transition_config:
            duration = sum(len_list) - sum([tr.duration if tr else 0 for tr in mixed_config.transition_config])
        else:
            duration = sum(len_list)

        # 构造返回体
        resp = MixedVideoResponse(
            message = f"{num} video being processed",
            video_url= obs_video_url,
            cover_img= obs_cover_url,
            duration= round(duration, 2),
            request_data = mixed_config.request_data,
            video_size = file_size,
            biz_id = mixed_config.biz_id
        )
        return resp