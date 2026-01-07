from datetime import datetime
from celery_mq.celery_app import celery_app
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest, ratio_option
from celery_mq.task_manager import task_manager
from core.normalize_process_pool import *
from utils.general_utils import *
from core.caption import *
from utils.log_utils import logger as log
import json
from service.mixed_video_service import mixed_video_service

@celery_app.task(queue="video_queue", bind=True)
def process_video_task(self, task_id: str):
    """
    处理视频任务

    Args:
        task_id: 任务ID（从RabbitMQ消息中获取）
    """
    try:
        # 更新任务状态为running
        task_manager.update_task_status(task_id, "running", started_at=datetime.now().isoformat())

        # 从Redis获取任务数据
        task_data = task_manager.get_task_data(task_id)
        if not task_data:
            error_msg = f"任务数据不存在: task_id={task_id}"
            log.error(error_msg)
            task_manager.update_task_status(task_id, "failed", error=error_msg)
            raise ValueError(error_msg)

        # 将字典转换为Pydantic模型
        mixed_config = MixedVideoRequest(**task_data)

        # 更新任务进度
        self.update_state(state='PROGRESS', meta={'progress': 0, 'message': '开始处理任务'})

        # 执行测试处理逻辑（用于测试任务创建和执行流程）
        _process_video_internal_test(mixed_config, task_id)

        # 任务完成，更新状态
        task_manager.update_task_status(task_id, "completed", completed_at=datetime.now().isoformat())
        self.update_state(state='SUCCESS', meta={'progress': 100, 'message': '任务完成'})

        log.info(f"任务处理完成: task_id={task_id}")

    except Exception as e:
        error_msg = f"任务处理失败: task_id={task_id}, error={str(e)}"
        log.error(error_msg, exc_info=True)
        task_manager.update_task_status(task_id, "failed", error=str(e), failed_at=datetime.now().isoformat())
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise


def _process_video_internal(mixed_config: MixedVideoRequest, task_id: str):
    """
    内部视频处理逻辑（原有代码）

    Args:
        mixed_config: 视频混剪配置
        task_id: 任务ID（用于更新进度）
    """
    project_id = "mix_" + str(random_with_system_time()) if not mixed_config.mix_id else "mix_" + str(
        mixed_config.mix_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")


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
    first_video_info = get_video_info(video_list[0], need_rotation=True)

    width, height, duration, rot, pix_format = first_video_info

    pix_fmt = "yuv422p10le" if pix_format == "yuv422p10le" else "yuv420p"

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
        cap_helper.gen_cap_mapping()
        log.debug(f"subtitle png cap list: {cap_helper.get_cap_list()}")

    normalize_thread_pool_results = process_pool_normalize(width, height, fps, video_list,
                                                            len_list, mixed_config, project_id,
                                                            pix_fmt=pix_fmt, cap_helper=cap_helper,
                                                            sticker_list=sticker_list)

    # log.info(f"normalized video: {normalize_thread_pool_results}")


def _process_video_internal_test(mixed_config: MixedVideoRequest, task_id: str):
    """
    测试用视频处理函数（不执行实际处理，直接返回成功）

    Args:
        mixed_config: 视频混剪配置
        task_id: 任务ID（用于更新进度）
    """
    log.info(f"[测试模式] 开始处理任务: task_id={task_id}")
    log.info(f"[测试模式] 任务配置信息:")
    log.info(f"  - 用户名称: {mixed_config.user_name}")
    log.info(f"  - 视频数量: {len(mixed_config.obs_video_path_list)}")
    log.info(f"  - FPS: {mixed_config.fps}")
    log.info(f"  - 分辨率: {mixed_config.resolution}")
    log.info(f"  - 比例类型: {mixed_config.ratio_type}")
    log.info(f"[测试模式] 任务配置详情: {json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
    log.info(f"[测试模式] 任务处理完成（模拟成功）: task_id={task_id}")
    # 不执行实际处理，直接返回成功
    return None