import asyncio
from datetime import datetime

from celery_mq.celery_app import celery_app
from models.pydantic_models.request.mixed_video_request import MixedVideoConfig, ratio_option
from service.video_service import *
from utils.general_utils import *
from utils.log_utils import logger as log
from config.config import *
from utils.caption_utils import *
import json

semaphore = asyncio.Semaphore(1)

@celery_app.task(queue="video_queue")
async def process_video_task(mixed_config: MixedVideoConfig,):
    project_id = "mix_" + str(random_with_system_time()) if not mixed_config.mix_id else "mix_" + str(
        mixed_config.mix_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")

    async with semaphore:
        fps = mixed_config.fps
        current_time = datetime.now()
        log.info(f"{len(mixed_config.obs_video_path_list)}个视频的混剪请求")
        log.info(f"于{current_time}收到请求体")
        log.info(f"{json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
        log.info(f"env: {my_config['env']}")

        obs_sub_folder = project_id
        log.info(f"config user_name: {mixed_config.user_name}")
        if mixed_config.user_name:
            now = datetime.now()
            # 格式化为 "年月日" 字符串（例如：20250619）
            date_str = now.strftime("%Y%m%d")
            log.info(f"{date_str}")  # 输出类似：20250619
            # 格式化为 "年月日时分秒" 字符串（例如：20250619143015）
            datetime_str = now.strftime("%Y%m%d%H%M%S")
            obs_sub_folder = mixed_config.user_name + "_" + datetime_str if ENV == "local" else f"{mixed_config.user_name}/output/mix_video/" + mixed_config.user_name + "_" + datetime_str
            log.info(f"detect current user info: {obs_sub_folder}")

        download_start = time.time()

        video_list = decode_path_list(mixed_config.obs_video_path_list, vpc=vpc)
        audio_list = decode_path_list(mixed_config.obs_audio_path_list, vpc=vpc)
        bgm_list = decode_path_list(mixed_config.obs_bgm_path_list, vpc=vpc)
        sticker_list = decode_path_list(mixed_config.obs_sticker_path_list, vpc=vpc)

        start_1 = time.time()
        video_list = [os.path.abspath(p) for p in video_list]
        log.info(f"download takes {time.time() - download_start} seconds")
        get_info_task = [asyncio.to_thread(get_video_info, video_list[0], need_rotation=True)]
        video_info_list = await asyncio.gather(*get_info_task)
        log.debug(f"video_info_list: {video_info_list}")
        width, height, duration, rot, pix_format = video_info_list[0]
        _, _, _, _, pix_format_list = zip(*video_info_list)
        pix_fmt = "yuv422p10le" if pix_format == "yuv422p10le" else "yuv420p"
        # if all([f == "yuv422p10le" for f in pix_format_list]):
        #     pix_fmt = "yuv422p10le"
        # elif all([f == "yuv420p10le" for f in pix_format_list]):
        #     pix_fmt = "yuv420p10le"
        log.info(f"first video is {mixed_config.obs_video_path_list[0]} have {rot} rotation")
        if abs(rot) in [90, 270]:
            # 交换横竖尺幅
            tmp = width
            width = height
            height = tmp
        log.info(f"rot {rot}")
        log.info(f"width: {width}")
        log.info(f"height: {height}")
        if not mixed_config.ratio_type:
            if width < height and height >= 1920:
                width = 1080
                height = 1920
            elif width > height and width >= 1920:
                width = 1920
                height = 1080
        if mixed_config.ratio_type and mixed_config.resolution:
            width, height = ratio_option[mixed_config.resolution][mixed_config.ratio_type]

        len_list = [(c.end - c.start) if c else 0 for c in
                    mixed_config.crop_config] if mixed_config.crop_config else [0] * len(video_list)
        log.info(f"video duration list: {len_list}")
        normalize_start = time.time()
        cap_helper = None
        if mixed_config.cap_config:
            cap_helper = CapHelper(project_id, width, height, mixed_config.cap_config)
            await cap_helper.gen_cap_mapping()
            log.debug(f"subtitle png cap list: {cap_helper.get_cap_list()}")

        normalize_thread_pool_results = await asyncio.to_thread(process_pool_normalize, width, height, fps, video_list,
                                                                len_list, mixed_config, project_id,
                                                                pix_fmt=pix_fmt, cap_helper=cap_helper,
                                                                sticker_list=sticker_list)

        # log.info(f"normalized video: {normalize_thread_pool_results}")