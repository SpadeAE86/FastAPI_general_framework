#!/bin/bash
# Celery Worker 启动脚本

# 激活虚拟环境（如果使用conda）
# conda activate video_mix

# 进入 src 目录
cd "$(dirname "$0")/src"

# 启动 Celery worker
celery -A celery_mq.celery_app worker --hostname=celery_local@%h --loglevel=INFO --queues=video_queue_dev --concurrency=4

