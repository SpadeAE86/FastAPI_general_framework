from celery import Celery

celery_app = Celery(
    "app",
    broker="memory://memory:6379/0",
    backend="memory://memory:6379/1",
)

# 告诉 Celery 去哪里找 task
celery_app.autodiscover_tasks(
    ["celery_mq.tasks"]  # 指向你写 task 的模块
)