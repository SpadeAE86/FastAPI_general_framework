import os
import socket
import ssl

from celery import Celery
from kombu import Queue, Exchange
from config.config import my_config, ENV
from utils.log_utils import logger as log

rabbitmq_config = my_config.get("rabbitmq", {}).get(ENV, {})
def get_rabbitmq_broker_url():
    """
    获取RabbitMQ broker URL
    
    从配置文件中读取RabbitMQ连接信息，构建AMQP格式的连接URL。
    如果虚拟主机(vhost)为根路径"/"，会自动编码为"%2F"。
    
    Returns:
        str: RabbitMQ broker连接URL，格式为 amqp://username:password@host:port/vhost
    """

    username = rabbitmq_config.get("username", "guest")
    password = rabbitmq_config.get("password", "guest")
    host = rabbitmq_config.get("host", "localhost")
    port = rabbitmq_config.get("port", 5672)
    vhost = rabbitmq_config.get("vhost", "/")
    use_ssl = rabbitmq_config.get("use_ssl", True)

    # 如果vhost是根路径，需要编码为%2F
    if vhost == "/":
        vhost = "%2F"
    scheme = "amqps" if use_ssl else "amqp"
    broker_url = f"{scheme}://{username}:{password}@{host}:{port}/{vhost}"
    log.info(f"RabbitMQ broker url: {broker_url}, port: {port}")
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
    include=["celery_mq.task.normalize_video_tasks", "celery_mq.task.alivoice_tasks"]
)
if rabbitmq_config.get("use_ssl", False):
    celery_app.conf.broker_use_ssl = {
        "ssl_version": ssl.PROTOCOL_TLS_CLIENT,
        "cert_reqs": ssl.CERT_NONE,
    }
import celery_mq.signals
# 从配置读取 Celery 参数
celery_config = my_config.get("celery", {})
queue_config = celery_config.get("queue", {})
task_config = celery_config.get("task", {})
worker_config = celery_config.get("worker", {})
broker_config = celery_config.get("broker", {})

# Celery配置
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_acks_late=False,  # 防止无限投递失败的请求体
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
    task_queues=(
        Queue(f"{ENV}_video_priority_queue", Exchange(queue_config.get("exchange", "tasks"), type=queue_config.get("exchange_type", "direct")), routing_key=queue_config.get("routing_key", "default"), queue_arguments={'x-max-priority': 10}),
    ),
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


