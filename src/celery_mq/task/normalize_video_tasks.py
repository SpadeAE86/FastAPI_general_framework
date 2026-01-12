from datetime import datetime
from utils.post_utils import post
from ffmpeg import run_async

import os
import time
import threading
import socket
from celery_mq.celery_app import celery_app
from celery.signals import worker_shutting_down
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


# 注册worker关闭信号处理
@worker_shutting_down.connect
def worker_shutting_down_handler(sender, sig, how, **kwargs):
    """
    当worker收到关闭信号时，标记当前任务以便重新分发

    注意：这个函数会在worker关闭时被调用，用于恢复正在执行的任务
    """
    log.warning(f"Worker收到关闭信号: sig={sig}, how={how}")

    try:
        # 获取当前worker名称和进程ID
        worker_name = socket.gethostname()
        pid = os.getpid()

        # 获取当前进程状态
        process_status = process_health_monitor.get_process_status(worker_name, pid)
        if process_status and process_status.get("current_task"):
            task_id = process_status.get("current_task")

            log.warning(f"Worker关闭，恢复任务状态: worker={worker_name}:{pid}, task_id={task_id}")

            # 获取任务信息
            task_info = task_manager.get_task_status(task_id)
            if task_info and task_info.get("status") == "running":
                # 将任务状态重置为pending
                task_manager.update_task_status(
                    task_id,
                    "pending",
                    error=f"Worker关闭（sig={sig}, how={how}），任务将重新分发"
                )

                # 将任务重新加入用户队列
                user_id = task_info.get("user_id")
                if user_id:
                    task_data = task_manager.get_task_data(task_id)
                    if task_data:
                        task_manager.add_task_to_user_queue(user_id, task_id, task_data)
                        log.info(f"任务已重新加入队列: task_id={task_id}, user_id={user_id}")
                    else:
                        log.error(f"无法获取任务数据，无法恢复任务: task_id={task_id}")
                else:
                    log.error(f"无法获取用户ID，无法恢复任务: task_id={task_id}")
    except Exception as e:
        log.error(f"处理worker关闭信号时出错: {e}", exc_info=True)


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

    resp: MixedVideoResponse = asyncio.run(mixed_video_service(mixed_config))     #业务逻辑
    #回调
    callback = my_config["callback"][ENV]["mixed"]
    callback_url = callback if not mixed_config.callback_url else mixed_config.callback_url
    asyncio.run(post(callback_url, resp.model_dump(), retry = 4, task_id=f"{project_id}"))

def _process_video_internal_test(mixed_config: MixedVideoRequest, task_id: str):
    """
    测试用视频处理函数（不执行实际处理，长时间sleep用于测试worker消失场景）

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
    log.info(f"[测试模式] 任务将sleep 60秒，用于测试worker消失场景: task_id={task_id}")

    # 长时间sleep，用于测试worker消失场景
    # 在测试中，可以在此期间杀死worker进程来验证任务重发机制
    time.sleep(60)

    log.info(f"[测试模式] 任务处理完成（模拟成功）: task_id={task_id}")
    # 不执行实际处理，直接返回成功
    return None