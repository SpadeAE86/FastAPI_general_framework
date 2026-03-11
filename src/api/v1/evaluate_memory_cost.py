from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Path

from celery_mq.celery_app import celery_app
from celery_mq.protocols import ProcessHealthMonitorProtocol
from core.health_monitor import process_health_monitor
from models.pydantic_models.request.evaluate_memory_request import EvaluateMemoryRequest
from models.pydantic_models.response.evaluate_memory_response import EvaluateMemoryResponse
from utils.log_utils import logger as log
from utils.process_utils import parse_process_id



memory_evaluate_router = APIRouter(prefix="/api/v1/video", tags=["general"])

# 模块级依赖，支持测试时替换
_health_monitor: ProcessHealthMonitorProtocol = process_health_monitor

def conservative_bpp(duration: float, width: int, height: int) -> float:
    """
    保守估计 bpp，覆盖大多数 NVENC H264 preset 12 视频
    高分辨率短视频会自动降低 bpp 避免过度预估
    """
    # 原始经验值
    if duration < 10:
        base_bpp = 0.38
    elif duration < 30:
        base_bpp = 0.35
    else:
        base_bpp = 0.33

    # 分辨率因子：高分辨率缩小 bpp
    # 以 640x360 为基准，缩放平方根防止线性放大
    resolution_factor = ((width * height) / (640 * 360)) ** 0.5

    # 高分辨率短视频降低 bpp，保证不超过 base_bpp
    adjusted_bpp = min(base_bpp, base_bpp / resolution_factor)

    return adjusted_bpp

@memory_evaluate_router.post("/memory_cost")
async def evaluate_memory(evaluate_memory_request: EvaluateMemoryRequest):
    duration = evaluate_memory_request.duration
    width = evaluate_memory_request.resolution_x
    height = evaluate_memory_request.resolution_y
    fps = evaluate_memory_request.fps

    bits_per_pixel = conservative_bpp(duration, int(width), int(height))

    memory_bytes = width * height * bits_per_pixel * fps * duration / 8
    memory_mb = memory_bytes / (1024 ** 2)

    return {
            "code": 200,
            "message": "success",
            "data": {
                "memory_mb": memory_mb
            }
        }
