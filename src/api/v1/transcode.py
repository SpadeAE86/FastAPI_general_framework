"""
雪碧图处理API路由

重构说明：通过模块级变量支持依赖注入，提高可测试性。
遵循依赖倒置原则 (DIP)。
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from celery_mq.protocols import TaskManagerProtocol
from celery_mq.task_manager import task_manager
from models.pydantic_models.request.transcode_video_request import TranscodeVideoRequest
from utils.log_utils import logger as log

transcode_router = APIRouter(prefix="/api/v1/video", tags=["video"])

# 模块级依赖，支持测试时替换
_task_manager: TaskManagerProtocol = task_manager


@transcode_router.post("/transcode")
async def create_transcode_task(
    transcode_request: TranscodeVideoRequest
) -> Dict[str, Any]:
    """
    创建视频转码任务（异步）

    Args:
        transcode_request: 转码请求体

    Returns:
        task_id 及任务状态
    """
    try:
        user_id = "anonymous"

        task_data = transcode_request.model_dump(exclude_none=True)
        task_data["task_type"] = "transcode"

        task_id = _task_manager.create_task(user_id, task_data)
        task_status = _task_manager.get_task_status(task_id)

        log.info(
            f"转码任务创建成功: task_id={task_id}, transcode_id={transcode_request.transcode_id}"
        )

        return {
            "code": 200,
            "message": "转码任务创建成功",
            "data": {
                "task_id": task_id,
                "task_type": "transcode",
                "status": task_status.get("status") if task_status else "pending",
                "created_at": task_status.get("created_at") if task_status else None,
                "transcode_id": transcode_request.transcode_id,
                "target_resolution": transcode_request.target_resolution,
                "trace_id": transcode_request.trace_id,
            },
        }
    except Exception as e:
        log.error(f"创建转码任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建转码任务失败: {str(e)}")
