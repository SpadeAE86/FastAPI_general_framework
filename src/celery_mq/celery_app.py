from celery import Celery
from config.config import my_config, ENV
from utils.log_utils import logger as log


def get_rabbitmq_broker_url():
    """获取RabbitMQ broker URL"""
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
    """获取Redis backend URL（用于结果存储）"""
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