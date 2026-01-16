"""
雪碧图处理API路由

重构说明：通过模块级变量支持依赖注入，提高可测试性。
遵循依赖倒置原则 (DIP)。
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from celery_mq.protocols import TaskManagerProtocol
from celery_mq.task_manager import task_manager
from models.pydantic_models.request.sprite_image_request import SpriteImageRequest
from utils.log_utils import logger as log

sprite_router = APIRouter(prefix="/api/v1/video", tags=["image"])

# 模块级依赖，支持测试时替换
_task_manager: TaskManagerProtocol = task_manager


@sprite_router.post("/sprite")
async def create_sprite_task(
    sprite_request: SpriteImageRequest
) -> Dict[str, Any]:
    """
    创建雪碧图生成任务（异步）

    Args:
        sprite_request: 雪碧图请求体

    Returns:
        task_id 及任务状态
    """
    try:
        user_id = "anonymous"

        task_data = sprite_request.model_dump(exclude_none=True)
        task_data["task_type"] = "sprite"

        task_id = _task_manager.create_task(user_id, task_data)
        task_status = _task_manager.get_task_status(task_id)

        log.info(
            f"雪碧图任务创建成功: task_id={task_id}, sprite_id={sprite_request.sprite_id}"
        )

        return {
            "code": 200,
            "message": "雪碧图任务创建成功",
            "data": {
                "task_id": task_id,
                "task_type": "sprite",
                "status": task_status.get("status") if task_status else "pending",
                "created_at": task_status.get("created_at") if task_status else None,
                "sprite_id": sprite_request.sprite_id,
                "trace_id": sprite_request.trace_id,
            },
        }
    except Exception as e:
        log.error(f"创建雪碧图任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建雪碧图任务失败: {str(e)}")