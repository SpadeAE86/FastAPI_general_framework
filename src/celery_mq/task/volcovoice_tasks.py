import asyncio
import json
import os
import socket
import threading
from datetime import datetime

from celery.signals import worker_shutting_down
from celery_mq.celery_app import celery_app
from celery_mq.task_manager import task_manager
from config.config import my_config, ENV
from core.celery_conponent.heartbeat import _heartbeat_loop
from core.health_monitor import process_health_monitor
from models.pydantic_models.request.volcovoice_request import Volcovoice_VO
from service.volcovoice_service import process_volcovoice_task
from utils.log_utils import logger as log
from utils.mq.rabbit_mq_producer import rabbitmq_producer_maker

celery_config = my_config.get("celery", {})
task_config = celery_config.get("task", {})

max_retries = task_config.get("max_retries", 3)
retry_countdown = task_config.get("retry_countdown", 10)
retry_backoff_max = task_config.get("retry_backoff_max", 300)

task2queue = my_config.get("task_type", {})
queue_name = task2queue.get("volcovoice", "volcovoice_queue")
result_queue = f"{ENV}_" + my_config.get("result_queue", {}).get("volcovoice", "volcovoice_result_queue")


@celery_app.task(
    queue=f"{ENV}_{queue_name}",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": max_retries, "countdown": retry_countdown},
    retry_backoff=True,
    retry_backoff_max=retry_backoff_max,
    retry_jitter=True,
)
def process_volcovoice_queue(self, data):
    trace_id = self.request.headers.get("trace_id", "")
    task_id = self.request.headers.get("task_id", "")

    if isinstance(data, str):
        if not task_id:
            task_id = data
        task_data = task_manager.get_task_data(task_id)
    elif isinstance(data, dict):
        task_data = data
    else:
        raise ValueError(f"Unsupported data type: {type(data)}")

    is_tracked = bool(task_id)
    if not is_tracked:
        import uuid

        task_id = f"ext_volcovoice_{uuid.uuid4().hex[:8]}"
        log.info(f"[外部调用] 生成临时 ID: {task_id}")

    if hasattr(self.request, "hostname") and self.request.hostname:
        worker_name = self.request.hostname
    else:
        worker_name = socket.gethostname()
    pid = os.getpid()

    heartbeat_stop_event = threading.Event()
    heartbeat_thread = None
    log.info(f"接收到 volcovoice 请求, trace_id={trace_id}, task_id={task_id}")

    try:
        if is_tracked:
            process_health_monitor.register_process(worker_name, pid)
            task_manager.update_task_status(task_id, "running", started_at=datetime.now().isoformat())
            task_manager.record_task_start_time(task_id)
            process_health_monitor.update_task_assignment(worker_name, pid, task_id)

            heartbeat_interval = my_config.get("process_health", {}).get("heartbeat_interval", 10)
            heartbeat_thread = threading.Thread(
                target=_heartbeat_loop,
                args=(worker_name, pid, heartbeat_stop_event, heartbeat_interval),
                name=f"HeartbeatThread-Volcovoice-{pid}",
                daemon=True,
            )
            heartbeat_thread.start()

        if not task_data:
            error_msg = f"任务数据不存在 task_id={task_id}"
            log.error(error_msg)
            if is_tracked:
                task_manager.update_task_status(task_id, "failed", error=error_msg)
            raise ValueError(error_msg)

        self.update_state(state="PROGRESS", meta={"progress": 0, "message": "开始处理火山音频任务"})

        voice_config = Volcovoice_VO.model_validate(task_data)
        log.info(f"音频处理请求体: {json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")

        response = asyncio.run(process_volcovoice_task(voice_config))
        result_data = response.model_dump(exclude_none=True)

        if is_tracked:
            task_manager.update_task_status(
                task_id,
                "completed",
                completed_at=datetime.now().isoformat(),
                result=result_data,
            )

        self.update_state(state="SUCCESS", meta={"progress": 100, "message": "任务完成"})
        log.info(f"火山音频任务处理完成: task_id={task_id}")

        headers = {"trace_id": trace_id, "task_id": task_id}
        video_mq_producer = rabbitmq_producer_maker()
        video_mq_producer.send(result_queue, message=result_data, headers=headers)
        log.info(f"成功推送到{result_queue}队列")
        return result_data

    except Exception as e:
        current_retry = getattr(self.request, "retries", 0)
        error_msg = f"火山音频任务处理失败 (重试次数: {current_retry}/{max_retries}): task_id={task_id}, error={str(e)}"
        if current_retry > 0:
            log.warning(f"[重试警告] 任务 task_id={task_id} 正在进行第 {current_retry} 次重试...")

        log.error(error_msg, exc_info=True)
        if is_tracked:
            task_manager.update_task_status(task_id, "failed", error=str(e), failed_at=datetime.now().isoformat())

        if getattr(self.request, "retries", 0) == max_retries:
            headers = {"trace_id": trace_id, "task_id": task_id}
            video_mq_producer = rabbitmq_producer_maker()
            biz_id = task_data.get("biz_id", 0) if isinstance(task_data, dict) else 0
            failure_data = {
                "biz_id": biz_id,
                "code": 100009,
                "message": f"failure due to {e}",
            }
            video_mq_producer.send(result_queue, message=failure_data, headers=headers)
            log.info(f"失败结果{failure_data}推送到{result_queue}队列")
        raise

    finally:
        if is_tracked:
            if heartbeat_thread:
                heartbeat_stop_event.set()
                heartbeat_thread.join(timeout=2)
            process_health_monitor.clear_task_assignment(worker_name, pid)
