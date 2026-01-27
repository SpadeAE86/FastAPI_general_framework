import asyncio
import json
import socket
import threading
from datetime import datetime

from celery.signals import worker_shutting_down
from utils.mq.rabbit_mq_producer import mq_producer
from celery_mq.celery_app import celery_app
from celery_mq.task_manager import task_manager
from config.config import my_config
from core.celery_conponent.heartbeat import _heartbeat_loop
from core.health_monitor import process_health_monitor
from core.video_processing.caption import *
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.mixed_video_response import MixedVideoResponse
from service.mixed_video_service import mixed_video_service
from utils.general_utils import *
from utils.log_utils import logger as log
from utils.post_utils import post

# 从配置读取任务重试参数
celery_config = my_config.get("celery", {})
task_config = celery_config.get("task", {})
queue_config = celery_config.get("queue", {})

# 获取任务重试配置
max_retries = task_config.get("max_retries", 3)
retry_countdown = task_config.get("retry_countdown", 10)
retry_backoff_max = task_config.get("retry_backoff_max", 300)
queue_name = queue_config.get("name", "video_queue")


@celery_app.task(
    queue=queue_name,
    bind=True,
    autoretry_for=(Exception,),  # 对所有异常自动重试
    retry_kwargs={'max_retries': max_retries, 'countdown': retry_countdown},  # 从配置读取重试参数
    retry_backoff=True,  # 指数退避
    retry_backoff_max=retry_backoff_max,  # 从配置读取最大退避时间
    retry_jitter=True,  # 添加随机抖动避免同时重试
)
def process_video_task(self, data):
    """
    处理视频任务

    Celery任务函数，处理视频任务

    负责执行视频混剪任务，包括：
    - 注册进程到健康监控系统
    - 更新任务状态
    - 启动心跳线程保持进程活跃
    - 从Redis获取任务数据并执行处理
    - 更新任务进度和状态

    Args:
        data: 任务数据(dict) 或 任务ID(str, 兼容旧版)
    """
    # 1. 解析参数
    task_id = self.request.headers.get("task_id")
    task_data = None
    
    if isinstance(data, str):
        # 旧模式兼容
        if not task_id: task_id = data
        task_data = task_manager.get_task_data(task_id)
    elif isinstance(data, dict):
        task_data = data
    else:
        raise ValueError(f"Unsupported data type: {type(data)}")

    # 标记是否为内部追踪任务
    is_tracked = bool(task_id)
    
    if not is_tracked:
        # 外部调用，生成临时 ID
        import uuid
        task_id = f"ext_mix_{uuid.uuid4().hex[:8]}"
        log.info(f"[外部调用] 生成临时 ID: {task_id}")

    # 获取worker名称和进程ID
    if hasattr(self.request, 'hostname') and self.request.hostname:
        worker_name = self.request.hostname
    else:
        # 使用socket获取主机名作为fallback
        worker_name = socket.gethostname()
    pid = os.getpid()

    # 心跳线程控制
    heartbeat_stop_event = threading.Event()
    heartbeat_thread = None

    try:
        if is_tracked:
            # 注册进程到Redis
            process_health_monitor.register_process(worker_name, pid)

            # 更新任务状态为running
            task_manager.update_task_status(task_id, "running", started_at=datetime.now().isoformat())

            # 记录任务分配时间
            task_manager.record_task_start_time(task_id)

            # 更新进程任务分配信息
            process_health_monitor.update_task_assignment(worker_name, pid, task_id)

            # 启动心跳线程
            heartbeat_interval = my_config.get("process_health", {}).get("heartbeat_interval", 10)
            heartbeat_thread = threading.Thread(
                target=_heartbeat_loop,
                args=(worker_name, pid, heartbeat_stop_event, heartbeat_interval),
                name=f"HeartbeatThread-{pid}",
                daemon=True
            )
            heartbeat_thread.start()

        # 检查数据
        if not task_data:
            error_msg = f"任务数据不存在: task_id={task_id}"
            log.error(error_msg)
            if is_tracked:
                task_manager.update_task_status(task_id, "failed", error=error_msg)
            raise ValueError(error_msg)


        # 更新任务进度
        self.update_state(state='PROGRESS', meta={'progress': 0, 'message': '开始处理任务'})

        # 执行测试处理逻辑（用于测试任务创建和执行流程）
        mixed_config: MixedVideoRequest  = MixedVideoRequest.model_validate(task_data)  # v2 的标准做法
        _process_video_internal(mixed_config, task_id)

        # 任务完成，更新状态
        if is_tracked:
            task_manager.update_task_status(task_id, "completed", completed_at=datetime.now().isoformat())
        
        self.update_state(state='SUCCESS', meta={'progress': 100, 'message': '任务完成'})

        log.info(f"任务处理完成: task_id={task_id}")

    except Exception as e:
        error_msg = f"任务处理失败: task_id={task_id}, error={str(e)}"
        log.error(error_msg, exc_info=True)
        if is_tracked:
            task_manager.update_task_status(task_id, "failed", error=str(e), failed_at=datetime.now().isoformat())
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        if is_tracked:
            # 停止心跳线程
            if heartbeat_thread:
                heartbeat_stop_event.set()
                heartbeat_thread.join(timeout=2)

            # 清除进程任务分配信息
            process_health_monitor.clear_task_assignment(worker_name, pid)

        # 注意：不在这里清理进程注册信息，因为进程可能还会执行其他任务
        # 进程退出时会自动清理（通过信号处理或监控服务检测）


def _process_video_internal(mixed_config: MixedVideoRequest, task_id: str):
    """
    内部视频处理逻辑（原有代码）

    执行实际的视频混剪处理，包括：
    - 下载视频、音频、背景音乐、贴纸等资源
    - 解析视频信息（分辨率、旋转角度等）
    - 生成字幕映射
    - 使用线程池进行视频标准化处理

    Args:
        mixed_config: 视频混剪配置，包含视频路径、音频路径、字幕配置等所有处理参数
        task_id: 任务ID，用于更新任务进度和日志记录
    """
    project_id = "mix_" + str(random_with_system_time()) if not mixed_config.biz_id else "mix_" + str(
        mixed_config.biz_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")

    current_time = datetime.now()
    log.info(f"{len(mixed_config.obs_video_path_list)}个视频的混剪请求")
    log.info(f"于{current_time}收到请求体")
    log.info(f"{json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
    log.info(f"env: {my_config['env']}")

    resp: MixedVideoResponse = asyncio.run(mixed_video_service(mixed_config))     #业务逻辑
    #回调
    callback = my_config["callback"][ENV]["mixed"]
    need_callback = my_config["need_callback"]
    if need_callback:
        asyncio.run(post(callback, resp.model_dump(), retry = 4, task_id=f"{project_id}"))
    result_queue = f"{ENV}_" + my_config["result_queue"]["sprite"]
    log.info(f"{mixed_config.biz_id} 任务完成: {resp.model_dump()}")
    mq_producer.send(result_queue, message=resp.model_dump())

def _process_video_internal_test(mixed_config: MixedVideoRequest, task_id: str):
    """
    测试用视频处理函数（不执行实际处理，长时间sleep用于测试worker消失场景）

    用于测试任务创建和执行流程，不执行实际的视频处理。
    通过长时间sleep模拟任务执行，可用于测试worker进程消失时的任务重发机制。

    Args:
        mixed_config: 视频混剪配置，包含视频路径、音频路径等配置信息（仅用于日志记录）
        task_id: 任务ID，用于日志记录和任务追踪

    Returns:
        None: 函数不返回有意义的结果，仅用于测试目的
    """
    log.info(f"[测试模式] 开始处理任务: task_id={task_id}")
    log.info(f"[测试模式] 任务配置信息:")
    log.info(f"  - 用户名称: {mixed_config.user_name}")
    log.info(f"  - 视频数量: {len(mixed_config.obs_video_path_list)}")
    log.info(f"  - FPS: {mixed_config.fps}")
    log.info(f"  - 分辨率: {mixed_config.resolution}")
    log.info(f"  - 比例类型: {mixed_config.ratio_type}")
    log.info(f"[测试模式] 任务配置详情: {json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
    log.info(f"[测试模式] 任务将sleep 60秒，用于测试worker消失场景: task_id={task_id}")

    # 长时间sleep，用于测试worker消失场景
    # 在测试中，可以在此期间杀死worker进程来验证任务重发机制
    time.sleep(60)

    log.info(f"[测试模式] 任务处理完成（模拟成功）: task_id={task_id}")
    # 不执行实际处理，直接返回成功
    return None
