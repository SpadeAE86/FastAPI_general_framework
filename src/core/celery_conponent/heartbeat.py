import os
import socket
import threading

from celery.signals import worker_shutting_down

from celery_mq.task_manager import task_manager
from utils.log_utils import logger as log
from core import process_health_monitor


def _heartbeat_loop(worker_name: str, pid: int, stop_event: threading.Event, interval: int):
    """
    心跳循环线程

    心跳循环线程函数

    在后台线程中定期更新进程心跳信息，用于健康监控系统检测进程是否存活。
    当stop_event被设置时，线程会退出循环。

    Args:
        worker_name: Worker名称，用于标识worker节点
        pid: 进程ID，用于标识具体的进程实例
        stop_event: 停止事件，当事件被设置时线程退出循环
        interval: 心跳间隔（秒），两次心跳更新之间的等待时间
    """
    while not stop_event.is_set():
        try:
            process_health_monitor.update_heartbeat(worker_name, pid)
            # 等待指定时间或被停止
            stop_event.wait(timeout=interval)
        except Exception as e:
            log.error(f"心跳更新失败: {worker_name}:{pid}, error={e}")
            # 即使出错也继续尝试
            stop_event.wait(timeout=interval)



