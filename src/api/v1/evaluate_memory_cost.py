from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Path

from celery_mq.celery_app import celery_app
from celery_mq.protocols import ProcessHealthMonitorProtocol
from core.health_monitor import process_health_monitor
from models.pydantic_models.request.evaluate_memory_request import EvaluateMemoryRequest
from models.pydantic_models.response.evaluate_memory_response import EvaluateMemoryResponse
from utils.log_utils import logger as log
from utils.process_utils import parse_process_id



memory_evaluate_router = APIRouter(prefix="/api/v1/process", tags=["process"])

# 模块级依赖，支持测试时替换
_health_monitor: ProcessHealthMonitorProtocol = process_health_monitor


@memory_evaluate_router.post("/memory_cost")
async def evaluate_memory(evaluate_memory_request: EvaluateMemoryRequest) -> EvaluateMemoryResponse:
    duration = evaluate_memory_request.duration
    width = evaluate_memory_request.resolution_x
    height = evaluate_memory_request.resolution_y
    fps = evaluate_memory_request.fps

    bits_per_pixel = 0.1  # nvenc_h264 preset=12

    memory_bytes = width * height * bits_per_pixel * fps * duration / 8
    memory_mb = memory_bytes / (1024 ** 2)

    return EvaluateMemoryResponse(
        code=0,
        message="ok",
        biz_id=0,
        memory_mb=round(memory_mb, 2)
    )
