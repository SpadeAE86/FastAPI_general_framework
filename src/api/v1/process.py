"""
进程状态查询API路由
"""
from fastapi import APIRouter, HTTPException, Path
from core.process_health_monitor import process_health_monitor
from celery_mq.celery_app import celery_app
from utils.log_utils import logger as log
from typing import Dict, Any, List

process_router = APIRouter(prefix="/api/v1/process", tags=["process"])


@process_router.get("/status")
async def get_all_process_status() -> Dict[str, Any]:
    """
    获取所有进程状态
    
    Returns:
        所有进程的状态信息
    """
    try:
        processes = process_health_monitor.get_all_processes()
        process_list = []
        
        for process_id in processes:
            try:
                parts = process_id.split(":", 1)
                if len(parts) != 2:
                    continue
                
                worker_name, pid_str = parts
                pid = int(pid_str)
                
                status = process_health_monitor.get_process_status(worker_name, pid)
                if status:
                    process_list.append(status)
            except (ValueError, KeyError) as e:
                log.error(f"获取进程状态失败: {process_id}, error={e}")
                continue
        
        return {
            "code": 200,
            "message": "查询成功",
            "data": {
                "processes": process_list,
                "total": len(process_list)
            }
        }
    except Exception as e:
        log.error(f"查询所有进程状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@process_router.get("/{worker_name}/{pid}")
async def get_process_status(
    worker_name: str = Path(..., description="Worker名称"),
    pid: int = Path(..., description="进程ID")
) -> Dict[str, Any]:
    """
    获取特定进程状态
    
    Args:
        worker_name: Worker名称
        pid: 进程ID
        
    Returns:
        进程状态信息
    """
    try:
        status = process_health_monitor.get_process_status(worker_name, pid)
        
        if not status:
            raise HTTPException(status_code=404, detail="进程不存在")
        
        return {
            "code": 200,
            "message": "查询成功",
            "data": status
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"查询进程状态失败: worker_name={worker_name}, pid={pid}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@process_router.post("/{worker_name}/{pid}/restart")
async def restart_process(
    worker_name: str = Path(..., description="Worker名称"),
    pid: int = Path(..., description="进程ID")
) -> Dict[str, Any]:
    """
    手动重启进程
    
    Args:
        worker_name: Worker名称
        pid: 进程ID
        
    Returns:
        重启结果
    """
    try:
        # 检查进程是否存在
        status = process_health_monitor.get_process_status(worker_name, pid)
        if not status:
            raise HTTPException(status_code=404, detail="进程不存在")
        
        # 使用Celery control API重启worker
        try:
            control = celery_app.control
            result = control.pool_restart(destination=[worker_name])
            
            log.info(f"手动重启进程: {worker_name}:{pid}, result={result}")
            
            return {
                "code": 200,
                "message": "重启命令已发送",
                "data": {
                    "worker_name": worker_name,
                    "pid": pid,
                    "result": str(result)
                }
            }
        except Exception as e:
            log.error(f"重启进程失败: {worker_name}:{pid}, error={e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"重启失败: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"重启进程操作失败: worker_name={worker_name}, pid={pid}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")

