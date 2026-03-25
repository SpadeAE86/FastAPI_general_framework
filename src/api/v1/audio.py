from fastapi import APIRouter, HTTPException, Header
from typing import Dict, Any
from utils.log_utils import logger as log
from celery_mq.protocols import TaskManagerProtocol
from celery_mq.task_manager import task_manager
from models.pydantic_models.request.alivoice_request import Alivoice_VO

audio_router = APIRouter(prefix="/api/v1/audio", tags=["audio"])
_task_manager: TaskManagerProtocol = task_manager

@audio_router.post("/alivoice")
async def create_alivoice_task(voice_config: Alivoice_VO, trace_id: str = Header(None)) -> Dict[str, Any]:
    """
    接收阿里云音频生成请求，创建任务并写入用户队列
    
    Args:
        voice_config: 音频生成配置
        trace_id: 追踪id
        
    Returns:
        包含task_id和状态的响应
    """
    try:
        # 从 BaseRequest 模型继承的字段中读取 user_id (通常由网关或拦截器注入)，并作为分发队列的参数
        user_id = str(voice_config.user_id) if voice_config.user_id else "default_user"
        
        task_data = voice_config.model_dump(exclude_none=True)
        task_data["task_type"] = "voice"
        task_data["trace_id"] = trace_id
        
        task_id = _task_manager.create_task(user_id, task_data)
        task_status = _task_manager.get_task_status(task_id)
        
        log.info(f"阿里云音频任务创建成功: task_id={task_id}, user_id={user_id}")
        
        return {
            "code": 200,
            "message": "阿里云音频任务创建成功",
            "data": {
                "task_id": task_id,
                "status": task_status.get("status") if task_status else "pending",
                "voice_id": str(voice_config.biz_id) if voice_config.biz_id else "0"
            }
        }
    except Exception as e:
        log.error(f"创建音频任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建音频任务失败: {str(e)}")

@audio_router.get("/task/{task_id}")
async def get_audio_task_status(task_id: str) -> Dict[str, Any]:
    """查询任务状态"""
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
