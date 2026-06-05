from typing import Any, Dict, Literal

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import select

from celery_mq.protocols import TaskManagerProtocol
from celery_mq.task_manager import task_manager
from database.mysql.mysql_manager import db_manager
from models.pydantic_models.db.volcovoice_sample import VolcovoiceSample
from models.pydantic_models.request.alivoice_request import Alivoice_VO
from models.pydantic_models.request.volcovoice_request import Volcovoice_VO
from utils.log_utils import logger as log

audio_router = APIRouter(prefix="/api/v1/audio", tags=["audio"])
_task_manager: TaskManagerProtocol = task_manager


def _create_audio_task(voice_config, task_type: str, trace_id: str | None) -> Dict[str, Any]:
    user_id = str(voice_config.user_id) if voice_config.user_id else "default_user"
    task_data = voice_config.model_dump(exclude_none=True)
    task_data["task_type"] = task_type
    task_data["trace_id"] = trace_id

    task_id = _task_manager.create_task(user_id, task_data)
    task_status = _task_manager.get_task_status(task_id)

    return {
        "code": 200,
        "message": "任务创建成功",
        "data": {
            "task_id": task_id,
            "status": task_status.get("status") if task_status else "pending",
            "biz_id": str(voice_config.biz_id) if voice_config.biz_id else "0",
        },
    }


@audio_router.post("/alivoice")
async def create_alivoice_task(voice_config: Alivoice_VO, trace_id: str = Header(None)) -> Dict[str, Any]:
    try:
        log.info(f"received trace_id={trace_id}")
        log.info(f"alivoice queue request: {voice_config.model_dump(exclude_none=True)}")
        return _create_audio_task(voice_config, "voice", trace_id)
    except Exception as e:
        log.error(f"创建阿里云音频任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建音频任务失败: {str(e)}")


@audio_router.post("/volcovoice")
async def create_volcovoice_task(voice_config: Volcovoice_VO, trace_id: str = Header(None)) -> Dict[str, Any]:
    try:
        log.info(f"received trace_id={trace_id}")
        log.info(f"volcovoice queue request: {voice_config.model_dump(exclude_none=True)}")
        return _create_audio_task(voice_config, "volcovoice", trace_id)
    except Exception as e:
        log.error(f"创建火山音频任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建音频任务失败: {str(e)}")


@audio_router.get("/models")
async def list_voice_models(
    model_type: Literal["all", "big", "small"] = Query(default="all", description="Filter model family"),
) -> Dict[str, Any]:
    try:
        async with db_manager.SessionLocal() as session:
            stmt = select(VolcovoiceSample).where(VolcovoiceSample.is_enabled == True).order_by(
                VolcovoiceSample.priority.desc(),
                VolcovoiceSample.voice_model_type.asc(),
                VolcovoiceSample.voice_character.asc(),
            )
            if model_type != "all":
                stmt = stmt.where(VolcovoiceSample.voice_model_type == model_type)
            result = await session.execute(stmt)
            rows = result.scalars().all()

        # Deduplicate voice characters (in case of multiple samples for the same character)
        seen = set()
        unique_rows = []
        for row in rows:
            pair = (row.voice_character, row.voice_model_type)
            if pair not in seen:
                seen.add(pair)
                unique_rows.append(row)

        def _to_item(row: VolcovoiceSample) -> dict[str, Any]:
            return {
                "id": row.id,
                "voice_character": row.voice_character,
                "voice_code": row.voice_code,
                "voice_model_type": row.voice_model_type,
                "note": row.note,
                "is_enabled": row.is_enabled,
                "priority": row.priority,
            }

        if model_type == "all":
            grouped: dict[str, list[dict[str, Any]]] = {"big": [], "small": []}
            for row in unique_rows:
                # Fallback model type to 'small' if not set
                model_key = row.voice_model_type if row.voice_model_type in ("big", "small") else "small"
                grouped.setdefault(model_key, []).append(_to_item(row))
            data: Any = grouped
        else:
            data = [_to_item(row) for row in unique_rows]

        return {"code": 200, "message": "ok", "data": data}
    except Exception as e:
        log.error(f"查询音色列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询音色列表失败: {str(e)}")


@audio_router.get("/task/{task_id}")
async def get_audio_task_status(task_id: str) -> Dict[str, Any]:
    try:
        task_status = _task_manager.get_task_status(task_id)
        if not task_status:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"code": 200, "message": "查询成功", "data": task_status}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"查询任务状态失败 task_id={task_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")
