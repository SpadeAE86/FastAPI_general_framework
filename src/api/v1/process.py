"""
进程状态查询API路由

重构说明：通过模块级变量支持依赖注入，提高可测试性。
遵循依赖倒置原则 (DIP)。
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Path

from celery_mq.celery_app import celery_app
from celery_mq.protocols import ProcessHealthMonitorProtocol
from core.health_monitor import process_health_monitor
from utils.log_utils import logger as log
from utils.process_utils import parse_process_id

process_router = APIRouter(prefix="/api/v1/process", tags=["process"])

# 模块级依赖，支持测试时替换
_health_monitor: ProcessHealthMonitorProtocol = process_health_monitor


@process_router.get("/status")
async def get_all_process_status() -> Dict[str, Any]:
    """
    获取所有进程状态
    
    Returns:
        所有进程的状态信息
    """
    try:
        processes = _health_monitor.get_all_processes()
        process_list = []
        
        for process_id in processes:
            try:
                # 解析进程ID
                parsed = parse_process_id(process_id)
                if parsed is None:
                    continue
                
                worker_name, pid = parsed
                
                status = _health_monitor.get_process_status(worker_name, pid)
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
        status = _health_monitor.get_process_status(worker_name, pid)
        
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
        status = _health_monitor.get_process_status(worker_name, pid)
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

