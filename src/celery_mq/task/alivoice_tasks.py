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
from models.pydantic_models.request.alivoice_request import Alivoice_VO
from models.pydantic_models.response.base_response import BaseResponse
from service.alivoice_service import process_alivoice_task
from utils.log_utils import logger as log
from utils.mq.rabbit_mq_producer import rabbitmq_producer_maker

# 从配置读取任务重试参数
celery_config = my_config.get("celery", {})
task_config = celery_config.get("task", {})
queue_config = celery_config.get("queue", {})

# 获取任务重试配置
max_retries = task_config.get("max_retries", 3)
retry_countdown = task_config.get("retry_countdown", 10)
retry_backoff_max = task_config.get("retry_backoff_max", 300)

task2queue = my_config.get("task_type", {})
queue_name = task2queue.get("voice", "voice_queue")
result_queue = f"{ENV}_" + my_config.get("result_queue", {}).get("voice", "voice_result_queue")

@celery_app.task(
    queue=f"{ENV}_{queue_name}",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': max_retries, 'countdown': retry_countdown},
    retry_backoff=True,
    retry_backoff_max=retry_backoff_max,
    retry_jitter=True,
)
def process_alivoice_queue(self, data):
    """
    处理阿里云音频任务
    
    负责执行音频TTS生成、拼接、上传任务，包括：
    - 注册进程到健康监控系统
    - 更新任务状态为 running
    - 启动心跳线程保持进程活跃
    - 执行服务层逻辑
    - 发送结果到消息队列
    """
    trace_id = self.request.headers.get("trace_id", "")
    task_id = self.request.headers.get("task_id", "")
    
    if isinstance(data, str):
        if not task_id: task_id = data
        task_data = task_manager.get_task_data(task_id)
    elif isinstance(data, dict):
        task_data = data
    else:
        raise ValueError(f"Unsupported data type: {type(data)}")
        
    is_tracked = bool(task_id)
    if not is_tracked:
        import uuid
        task_id = f"ext_voice_{uuid.uuid4().hex[:8]}"
        log.info(f"[外部调用] 生成临时 ID: {task_id}")

    if hasattr(self.request, 'hostname') and self.request.hostname:
        worker_name = self.request.hostname
    else:
        worker_name = socket.gethostname()
    pid = os.getpid()

    heartbeat_stop_event = threading.Event()
    heartbeat_thread = None
    log.info(f"接收到 alivoice 请求, trace_id={trace_id}, task_id={task_id}")
    
    try:
        if is_tracked:
            # 注册进程到Redis
            process_health_monitor.register_process(worker_name, pid)
            # 更新任务状态为 running
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
                name=f"HeartbeatThread-Voice-{pid}",
                daemon=True
            )
            heartbeat_thread.start()

        if not task_data:
            error_msg = f"任务数据不存在: task_id={task_id}"
            log.error(error_msg)
            if is_tracked:
                task_manager.update_task_status(task_id, "failed", error=error_msg)
            raise ValueError(error_msg)

        self.update_state(state='PROGRESS', meta={'progress': 0, 'message': '开始处理音频任务'})

        voice_config = Alivoice_VO.model_validate(task_data)
        log.info(f"音频处理请求体: {json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
        
        # Async execution block
        response = asyncio.run(process_alivoice_task(voice_config))
        result_data = response.model_dump(exclude_none=True)

        # Update valid status
        if is_tracked:
            task_manager.update_task_status(task_id, "completed", completed_at=datetime.now().isoformat(), result=result_data)
            
        self.update_state(state='SUCCESS', meta={'progress': 100, 'message': '任务完成'})

        log.info(f"音频任务处理完成: task_id={task_id}")
        
        # Push to MQ
        headers = {"trace_id": trace_id, "task_id": task_id}
        video_mq_producer = rabbitmq_producer_maker()
        video_mq_producer.send(result_queue, message=result_data, headers=headers)
        log.info(f"成功推送到{result_queue}队列")
        
        return result_data

    except Exception as e:
        current_retry = getattr(self.request, 'retries', 0)
        error_msg = f"音频任务处理失败 (重试次数: {current_retry}/{max_retries}): task_id={task_id}, error={str(e)}"
        if current_retry > 0:
            log.warning(f"[重试告警] 任务 task_id={task_id} 正在进行第 {current_retry} 次重试...")
            
        log.error(error_msg, exc_info=True)
        if is_tracked:
            task_manager.update_task_status(task_id, "failed", error=str(e), failed_at=datetime.now().isoformat())
            
        if getattr(self.request, 'retries', 0) == max_retries:
            headers = {"trace_id": trace_id, "task_id": task_id}
            video_mq_producer = rabbitmq_producer_maker()
            biz_id = task_data.get("biz_id", 0) if isinstance(task_data, dict) else 0
            
            failure_data = {
                "biz_id": biz_id, 
                "code": 100009, 
                "message": f"failure due to {e}"
            }
            video_mq_producer.send(
                result_queue,
                message=failure_data,
                headers=headers
            )
            log.info(f"失败结果{failure_data}推送到{result_queue}队列")
        raise
        
    finally:
        if is_tracked:
            if heartbeat_thread:
                heartbeat_stop_event.set()
                heartbeat_thread.join(timeout=2)
            process_health_monitor.clear_task_assignment(worker_name, pid)
