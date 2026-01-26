import asyncio
import os
import socket
import threading
from datetime import datetime
import logging

from celery_mq.task_manager import task_manager
from config.config import my_config, ENV
from models.pydantic_models.request.transcode_video_request import TranscodeVideoRequest
from models.pydantic_models.response.transcode_video_response import TranscodeVideoResponse
from service.transcode_video_service import transcode_video_service
from utils.general_utils import random_with_system_time
from utils.mq.rabbit_mq_producer import mq_producer
from utils.post_utils import post
from utils.tencent.cos_uploader import vod_upload_to_cos

from core import process_health_monitor
from core.celery_conponent.heartbeat import _heartbeat_loop

from celery_mq.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(
    queue=f"{ENV}_" + my_config.get("task_type", {}).get("transcode", "transcode_queue"),
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 10},
    retry_backoff=True,
    retry_jitter=True
)
def process_transcode_task(self, data):
    """
    Celery 任务函数：处理 transcode 任务
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
        task_id = f"ext_trans_{uuid.uuid4().hex[:8]}"
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

        # 获取任务数据
        if not task_data:
            error_msg = f"任务数据不存在: task_id={task_id}"
            log.error(error_msg)
            if is_tracked:
                task_manager.update_task_status(task_id, "failed", error=error_msg)
            raise ValueError(error_msg)

        # 更新任务进度
        self.update_state(state='PROGRESS', meta={'progress': 0, 'message': '开始处理转码任务'})

        # 核心处理
        transcode_request: TranscodeVideoRequest = TranscodeVideoRequest.model_validate(task_data)  # v2 的标准做法
        _process_transcode_internal(transcode_request, task_id)

        # 任务完成
        if is_tracked:
            task_manager.update_task_status(task_id, "completed", completed_at=datetime.now().isoformat())
        
        self.update_state(state='SUCCESS', meta={'progress': 100, 'message': '任务完成'})

        log.info(f"Transcode 任务处理完成: task_id={task_id}")

    except Exception as e:
        error_msg = f"Transcode 任务处理失败: task_id={task_id}, error={str(e)}"
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

def _process_transcode_internal(transcode_request: TranscodeVideoRequest, task_id: str):
    """
    核心处理逻辑：提交视频到腾讯 VOD 上传并轮询结果
    """
    project_id = "transcode_" + str(random_with_system_time()) if not transcode_request.transcode_id else "transcode_" + str(
        transcode_request.transcode_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")
    video_path = transcode_request.obs_video_path

    if not video_path or not isinstance(video_path, str):
        raise ValueError(f"任务缺少 video_path: task_id={task_id}")

    # 初始化 VOD 上传器
    resp: TranscodeVideoResponse = asyncio.run(transcode_video_service(transcode_request))
    #回调
    callback = my_config["callback"][ENV]["transcode"]
    need_callback = my_config["need_callback"]


    if need_callback:
        asyncio.run(post(callback, resp.model_dump(), retry = 4, task_id=f"{project_id}"))
    result_queue = f"{ENV}_" + my_config["result_queue"]["transcode"]
    log.info(f"{transcode_request.transcode_id} 任务完成: {resp.model_dump()}")
    mq_producer.send(result_queue, message=resp.model_dump())



