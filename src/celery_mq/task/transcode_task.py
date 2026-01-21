import os
import socket
import threading
from datetime import datetime
import logging
from utils.tencent.vod_uploader import TencentVodUploader
from celery_mq.task_manager import task_manager
from config.config import my_config, ENV
from utils.tencent.cos_uploader import vod_upload_to_cos

from core import process_health_monitor
from core.celery_conponent.heartbeat import _heartbeat_loop

from celery_mq.celery_app import celery_app

log = logging.getLogger(__name__)

def _process_transcode_internal(task_data: dict, task_id: str):
    """
    核心处理逻辑：提交视频到腾讯 VOD 上传并轮询结果
    """
    video_path = task_data.get("video_path")
    if not video_path or not isinstance(video_path, str):
        raise ValueError(f"任务缺少 video_path: task_id={task_id}")

    # 初始化 VOD 上传器
    uploader = TencentVodUploader(
        secret_id=task_data.get("secret_id"),
        secret_key=task_data.get("secret_key"),
        sub_app_id=task_data.get("sub_app_id")
    )

    # 1. 申请上传
    apply_resp = uploader.apply_upload(video_path=video_path, media_type="mp4")
    vod_session_key = apply_resp["VodSessionKey"]
    log.info(f"申请上传成功: task_id={task_id}, VodSessionKey={vod_session_key}")

    # 2. 上传到 COS
    vod_upload_to_cos(apply_resp, video_path)
    log.info(f"视频已上传到 COS: task_id={task_id}")

    # 3. 提交上传并轮询结果
    transcode_result = uploader.commit_and_poll(vod_session_key)
    media_url = transcode_result.get("MediaUrl")
    if not media_url:
        raise RuntimeError(f"Transcode 完成但未返回 MediaUrl: task_id={task_id}")

    log.info(f"转码完成: task_id={task_id}, media_url={media_url}")

    return transcode_result


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
        transcode_result = _process_transcode_internal(task_data, task_id)

        # 任务完成
        if is_tracked:
            task_manager.update_task_status(task_id, "completed", completed_at=datetime.now().isoformat(), result=transcode_result)
        
        self.update_state(state='SUCCESS', meta={'progress': 100, 'message': '任务完成'})

        log.info(f"Transcode 任务处理完成: task_id={task_id}")

        return transcode_result

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
