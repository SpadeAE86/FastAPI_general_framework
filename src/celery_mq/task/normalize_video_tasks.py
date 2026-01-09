from datetime import datetime
from utils.post_utils import post
from ffmpeg import run_async

from celery_mq.celery_app import celery_app
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest, ratio_option
from celery_mq.task_manager import task_manager
from core.video_processing.normalize_process_pool import *
from core.health_monitor import process_health_monitor
from models.pydantic_models.response.mixed_video_response import MixedVideoResponse
from service.mixed_video_service import mixed_video_service
from utils.general_utils import *
from core.video_processing.caption import *
from utils.log_utils import logger as log
from config.config import my_config
import json
import threading
import asyncio

@celery_app.task(queue="video_queue", bind=True)
def process_video_task(self, task_id: str):
    """
    处理视频任务

    Args:
        task_id: 任务ID（从RabbitMQ消息中获取）
    """
    # 获取worker名称和进程ID
    if hasattr(self.request, 'hostname') and self.request.hostname:
        worker_name = self.request.hostname
    else:
        # 使用socket获取主机名作为fallback
        import socket
        worker_name = socket.gethostname()
    pid = os.getpid()

    # 心跳线程控制
    heartbeat_stop_event = threading.Event()
    heartbeat_thread = None

    try:
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
        _process_video_internal(mixed_config, task_id)

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
    finally:
        # 停止心跳线程
        if heartbeat_thread:
            heartbeat_stop_event.set()
            heartbeat_thread.join(timeout=2)

        # 清除进程任务分配信息
        process_health_monitor.clear_task_assignment(worker_name, pid)

        # 注意：不在这里清理进程注册信息，因为进程可能还会执行其他任务
        # 进程退出时会自动清理（通过信号处理或监控服务检测）


def _heartbeat_loop(worker_name: str, pid: int, stop_event: threading.Event, interval: int):
    """
    心跳循环线程

    Args:
        worker_name: Worker名称
        pid: 进程ID
        stop_event: 停止事件
        interval: 心跳间隔（秒）
    """
    while not stop_event.is_set():
        try:
            process_health_monitor.update_heartbeat(worker_name, pid)
            # 等待指定时间或被停止
            stop_event.wait(timeout=interval)
        except Exception as e:
            log.error(f"心跳更新失败: {worker_name}:{pid}, error={e}")
            # 即使出错也继续尝试
            stop_event.wait(timeout=interval)


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

    current_time = datetime.now()
    log.info(f"{len(mixed_config.obs_video_path_list)}个视频的混剪请求")
    log.info(f"于{current_time}收到请求体")
    log.info(f"{json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
    log.info(f"env: {my_config['env']}")

    resp: MixedVideoResponse = asyncio.run(mixed_video_service(mixed_config))
    callback = my_config["callback"][ENV]["mixed"]
    callback_url = callback if not mixed_config.callback_url else mixed_config.callback_url
    asyncio.run(post(callback_url, resp.model_dump(), retry = 4, task_id=f"{project_id}"))

def _process_video_internal_test(mixed_config: MixedVideoRequest, task_id: str):
    """
    测试用视频处理函数（不执行实际处理，直接返回成功）

    Args:
        mixed_config: 视频混剪配置
        task_id: 任务ID（用于更新进度）
    """
    time.sleep(100)
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