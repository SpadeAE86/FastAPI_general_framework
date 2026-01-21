import os
import socket
import threading
from datetime import datetime
import logging

from celery_mq.celery_app import celery_app
from celery_mq.task_manager import task_manager
from config.config import my_config, ENV
from core.video_processing.sprite import generate_sprite

from core import process_health_monitor
from core.celery_conponent.heartbeat import _heartbeat_loop

log = logging.getLogger(__name__)


@celery_app.task(
    queue= f"{ENV}_" + my_config.get("task_type", {}).get("sprite", "sprite_queue"),
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': my_config.get("celery", {}).get("task", {}).get("max_retries", 3),
                  'countdown': my_config.get("celery", {}).get("task", {}).get("retry_countdown", 10)},
    retry_backoff=True,
    retry_backoff_max=my_config.get("celery", {}).get("task", {}).get("retry_backoff_max", 300),
    retry_jitter=True
)
def process_sprite_task(self, data):
    """
    Celery 任务函数：生成视频雪碧图
    """
    # 1. 解析参数
    task_id = self.request.headers.get("task_id")
    task_data = None
    
    # 兼容性处理
    if isinstance(data, str):
        # 旧模式：参数是 task_id
        if not task_id:
            task_id = data
        # 从 Redis 获取数据
        task_data = task_manager.get_task_data(task_id)
    elif isinstance(data, dict):
        # 新模式：参数是 task_data
        task_data = data
        # task_id 优先取 header，没有的话说明是外部调用
    else:
        log.error(f"收到不支持的数据类型: {type(data)}")
        raise ValueError(f"Unsupported data type: {type(data)}")

    # 标记是否为内部追踪任务（有 task_id 且非外部临时调用）
    is_tracked = bool(task_id)
    
    if not is_tracked:
        # 外部调用，生成临时 ID
        import uuid
        task_id = f"ext_{uuid.uuid4().hex[:8]}"
        log.info(f"[外部调用] 生成临时 ID: {task_id}")

    # 获取worker名称和进程ID
    if hasattr(self.request, 'hostname') and self.request.hostname:
        worker_name = self.request.hostname
    else:
        worker_name = socket.gethostname()
    pid = os.getpid()

    # 心跳线程控制
    heartbeat_stop_event = threading.Event()
    heartbeat_thread = None

    try:
        if is_tracked:
            # 注册进程到Redis监控
            process_health_monitor.register_process(worker_name, pid)

            # 更新任务状态为 running
            task_manager.update_task_status(task_id, "running", started_at=datetime.now().isoformat())

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

        # 更新任务进度 (Celery 自身状态)
        self.update_state(state='PROGRESS', meta={'progress': 0, 'message': '开始生成雪碧图'})

        # 核心处理
        sprite_paths = _process_sprite_internal(task_data, task_id)

        # 任务完成
        if is_tracked:
            task_manager.update_task_status(task_id, "completed", completed_at=datetime.now().isoformat(), result={"sprite_paths": sprite_paths})
        
        self.update_state(state='SUCCESS', meta={'progress': 100, 'message': '任务完成'})

        log.info(f"雪碧图任务处理完成: task_id={task_id}")
        return sprite_paths

    except Exception as e:
        error_msg = f"雪碧图任务处理失败: task_id={task_id}, error={str(e)}"
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




def _process_sprite_internal(task_data: dict, task_id: str):
    """
    核心处理逻辑：生成雪碧图
    """
    video_path = task_data.get("video_path")
    if not video_path or not isinstance(video_path, str):
        raise ValueError(f"任务缺少 video_path: task_id={task_id}")

    # 调用核心函数生成雪碧图
    sprite_paths = generate_sprite(video_path, task_id)
    if not sprite_paths:
        raise RuntimeError(f"生成雪碧图失败: task_id={task_id}")

    log.info(f"生成雪碧图成功: task_id={task_id}, count={len(sprite_paths)}")
    return sprite_paths