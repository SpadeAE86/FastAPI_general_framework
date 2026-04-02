"""
视频处理API路由

重构说明：通过模块级变量支持依赖注入，提高可测试性。
遵循依赖倒置原则 (DIP)。
"""
from fastapi import APIRouter, HTTPException, Path, Header
from celery_mq.protocols import TaskManagerProtocol
from models.pydantic_models.request.frontend_timeline_request import FrontendTimelineRequest
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from celery_mq.task_manager import task_manager
from utils.log_utils import logger as log
from typing import Dict, Any, List, Optional

video_router = APIRouter(prefix="/api/v1/video", tags=["video"])

# 模块级依赖，支持测试时替换
_task_manager: TaskManagerProtocol = task_manager


@video_router.post("/edit")
async def create_video_task(mixed_config: MixedVideoRequest, trace_id = Header(None)) -> Dict[str, Any]:
    """
    接收视频剪辑请求，创建任务并写入用户队列

    Args:
        mixed_config: 视频混剪配置
        trace_id: 追踪id
        
    Returns:
        包含task_id和状态的响应
    """
    try:
        # 从请求中获取user_name作为user_id
        user_id = f"{mixed_config.user_id}"
        
        # 将Pydantic模型转换为字典
        task_data = mixed_config.model_dump(exclude_none=True)
        task_data["task_type"] = "mix"
        task_data["trace_id"] = trace_id

        # 创建任务
        task_id = _task_manager.create_task(user_id, task_data)
        
        # 获取任务状态
        task_status = _task_manager.get_task_status(task_id)
        
        log.info(f"混剪任务创建成功: task_id={task_id}, user_id={user_id}, biz_id={mixed_config.biz_id}")
        
        return {
            "code": 200,
            "message": "任务创建成功",
            "data": {
                "task_id": task_id,
                "status": task_status.get("status") if task_status else "pending",
                "created_at": task_status.get("created_at") if task_status else None,
                "trace_id": trace_id,
                "biz_id": mixed_config.biz_id,
            }
        }
    except Exception as e:
        log.error(f"创建任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@video_router.get("/task/{task_id}")
async def get_task_status(task_id: str = Path(..., description="任务ID")) -> Dict[str, Any]:
    """
    查询任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务状态信息
    """
    try:
        task_status = _task_manager.get_task_status(task_id)
        
        if not task_status:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "code": 200,
            "message": "查询成功",
            "data": task_status
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"查询任务状态失败: task_id={task_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")


@video_router.get("/task/{task_id}/subtasks")
async def get_task_subtasks(task_id: str = Path(..., description="任务ID")) -> Dict[str, Any]:
    """
    查询子任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        子任务列表
    """
    try:
        # 先检查任务是否存在
        task_status = _task_manager.get_task_status(task_id)
        if not task_status:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取子任务列表
        subtasks = _task_manager.get_task_subtasks(task_id)
        
        return {
            "code": 200,
            "message": "查询成功",
            "data": {
                "task_id": task_id,
                "subtasks": subtasks
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"查询子任务失败: task_id={task_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询子任务失败: {str(e)}")


@video_router.delete("/task/{task_id}")
async def delete_task(task_id: str = Path(..., description="任务ID")) -> Dict[str, Any]:
    """
    删除指定任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        删除结果
    """
    try:
        success = _task_manager.delete_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="任务不存在")
            
        return {
            "code": 200,
            "message": "删除成功",
            "data": {
                "task_id": task_id
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"删除任务失败: task_id={task_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")

@video_router.post("/frontend-timeline", response_model=Dict[str, Any])
async def get_frontend_timeline(request: FrontendTimelineRequest) -> Dict[str, Any]:
    """
    生成前端时间线JSON配置
    """
    try:
        timeline_res = build_frontend_timeline(
            req=request.mixed_request,
            fps_list=request.fps_list,
            sprites_list=request.sprites_list
        )
        return {
            "code": 200,
            "message": "生成成功",
            "data": timeline_res.model_dump(exclude_none=True)
        }
    except Exception as e:
        log.error(f"生成前端Timeline失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成前端Timeline失败: {str(e)}")