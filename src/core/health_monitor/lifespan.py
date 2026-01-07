"""
健康监控服务生命周期管理：在FastAPI中启动和停止监控服务
"""
from core.health_monitor.service import health_monitor_service
from utils.log_utils import logger as log


def start_health_monitor():
    """启动健康监控服务"""
    try:
        health_monitor_service.start()
        log.info("健康监控服务已在FastAPI中启动")
    except Exception as e:
        log.error(f"启动健康监控服务失败: {e}", exc_info=True)


def stop_health_monitor():
    """停止健康监控服务"""
    try:
        health_monitor_service.stop()
        log.info("健康监控服务已在FastAPI中停止")
    except Exception as e:
        log.error(f"停止健康监控服务失败: {e}", exc_info=True)

