#!/bin/bash
# Celery Worker 启动脚本

# 激活虚拟环境（如果使用conda）
#conda activate video_mix

# 进入 src 目录
cd "$(dirname "$0")/src"
# 启动 Celery worker

/root/miniconda3/envs/test_gpu/bin/python -m celery -A celery_mq.celery_app worker --hostname=celery_test@%h --loglevel=INFO --queues=test_video_queue --concurrency=1

