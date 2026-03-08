"""
健康监控服务生命周期管理：在FastAPI中启动和停止监控服务
"""
from core.health_monitor.service import health_monitor_service
from utils.cache_utils import start_cleanup_thread
from utils.log_utils import logger as log


def start_health_monitor():
    """
    启动健康监控服务

    在FastAPI应用启动时调用，启动健康监控服务的所有检查线程和指标上报服务。
    """
    try:
        health_monitor_service.start()
        log.info("健康监控服务已在FastAPI中启动")
    except Exception as e:
        log.error(f"启动健康监控服务失败: {e}", exc_info=True)

    try:
        # 启动 diskcache 后台清理线程：每 60 秒执行 expire + gc_files
        # expire  → 清掉 SQLite 里过期的条目（key 已失效）
        # gc_files → 扫描 _FILES_DIR，删除已不在 cache 里的孤立物理文件
        log.info("OBS 文件缓存清理线程已启动")
    except Exception as e:
        log.error(f"启动缓存清理线程失败: {e}", exc_info=True)


def stop_health_monitor():
    """
    停止健康监控服务

    在FastAPI应用关闭时调用，停止健康监控服务的所有检查线程和指标上报服务。
    """
    try:
        health_monitor_service.stop()
        log.info("健康监控服务已在FastAPI中停止")
    except Exception as e:
        log.error(f"停止健康监控服务失败: {e}", exc_info=True)
