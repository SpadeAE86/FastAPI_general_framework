import os
import socket

from celery import Celery
from celery.signals import worker_shutting_down

from celery_mq.task_manager import task_manager
from config.config import my_config, ENV
from core import process_health_monitor
from utils.log_utils import logger as log


def get_rabbitmq_broker_url():
    """
    获取RabbitMQ broker URL
    
    从配置文件中读取RabbitMQ连接信息，构建AMQP格式的连接URL。
    如果虚拟主机(vhost)为根路径"/"，会自动编码为"%2F"。
    
    Returns:
        str: RabbitMQ broker连接URL，格式为 amqp://username:password@host:port/vhost
    """
    rabbitmq_config = my_config.get("rabbitmq", {}).get(ENV, {})
    username = rabbitmq_config.get("username", "guest")
    password = rabbitmq_config.get("password", "guest")
    host = rabbitmq_config.get("host", "localhost")
    port = rabbitmq_config.get("port", 5672)
    vhost = rabbitmq_config.get("vhost", "/")

    # 如果vhost是根路径，需要编码为%2F
    if vhost == "/":
        vhost = "%2F"

    broker_url = f"amqp://{username}:{password}@{host}:{port}/{vhost}"
    return broker_url


def get_redis_backend_url():
    """
    获取Redis backend URL（用于结果存储）
    
    从配置文件中读取Redis连接信息，构建Redis格式的连接URL。
    用于Celery任务结果的存储和查询。
    
    Returns:
        str: Redis backend连接URL，格式为 redis://host:port/db 或 redis://:password@host:port/db
    """
    redis_config = my_config.get("redis", {}).get(ENV, {})
    host = redis_config.get("host", "127.0.0.1")
    port = redis_config.get("port", 6379)
    db = redis_config.get("database", 0)
    password = redis_config.get("password", "")

    if password:
        backend_url = f"redis://:{password}@{host}:{port}/{db}"
    else:
        backend_url = f"redis://{host}:{port}/{db}"

    return backend_url


broker_url = get_rabbitmq_broker_url()
backend_url = get_redis_backend_url()

log.info(f"Celery broker URL: {broker_url}")
log.info(f"Celery backend URL: {backend_url}")

celery_app = Celery(
    "app",
    broker=broker_url,
    backend=backend_url,
    include=["celery_mq.task.normalize_video_tasks"]
)

# 从配置读取 Celery 参数
celery_config = my_config.get("celery", {})
queue_config = celery_config.get("queue", {})
task_config = celery_config.get("task", {})
worker_config = celery_config.get("worker", {})
broker_config = celery_config.get("broker", {})

# Celery配置
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_acks_late=True,  # 任务完成后才确认
    task_reject_on_worker_lost=True,  # Worker丢失时重新分发
    task_default_message_ttl=task_config.get("message_ttl", 3600000),  # 消息TTL：1小时（毫秒）
    task_default_exchange=queue_config.get("exchange", "tasks"),
    task_default_exchange_type=queue_config.get("exchange_type", "direct"),
    task_default_routing_key=queue_config.get("routing_key", "default"),
    task_default_delivery_mode=2,  # 持久化消息
    task_time_limit=task_config.get("time_limit", 3600),  # 任务硬超时：1小时
    task_soft_time_limit=task_config.get("soft_time_limit", 3300),  # 任务软超时：55分钟
    worker_prefetch_multiplier=worker_config.get("prefetch_multiplier", 1),  # 每个worker只预取1个任务
    worker_max_tasks_per_child=worker_config.get("max_tasks_per_child", 50),  # 每个worker进程最多处理50个任务后重启，避免内存泄漏
    worker_disable_rate_limits=True,  # 禁用速率限制
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # RabbitMQ连接配置
    # 注意：RabbitMQ不使用visibility_timeout（这是SQS的概念）
    # RabbitMQ通过task_acks_late和task_reject_on_worker_lost来处理消息重分发
    broker_transport_options={
        'max_retries': broker_config.get("max_retries", 3),
        'interval_start': broker_config.get("interval_start", 0),
        'interval_step': broker_config.get("interval_step", 0.2),
        'interval_max': broker_config.get("interval_max", 0.2),
        'priority_steps': list(range(10)),  # 支持优先级
        'sep': ':',
        'queue_order_strategy': 'priority',  # 优先级队列策略
    },
)

# 告诉 Celery 去哪里找 task
celery_app.autodiscover_tasks(
    ["celery_mq.task"]  # 指向你写 task 的模块
)

# 注册worker关闭信号处理
@worker_shutting_down.connect
def worker_shutting_down_handler(sender, sig, how, **kwargs):
    """
    Worker关闭信号处理器

    当worker收到关闭信号时，自动恢复正在执行的任务状态，将任务重新加入队列以便重新分发。
    这是Celery信号处理器，会在worker关闭时自动触发。

    Args:
        sender: 信号发送者对象
        sig: 信号编号，表示收到的系统信号
        how: 关闭方式，表示如何关闭worker
        **kwargs: 其他关键字参数，Celery信号系统传递的额外信息
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
