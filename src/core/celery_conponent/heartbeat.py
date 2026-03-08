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

# 注册worker关闭信号处理
@worker_shutting_down.connect
def worker_shutting_down_handler(sender, sig, how, **kwargs):
    """
    Worker关闭信号处理器

    当worker收到关闭信号时，自动恢复正在执行的任务状态，将任务重新加入队列以便重新分发。
    这是Celery信号处理器，会在worker关闭时自动触发。

    Args:
        sender: 信号发送者对象
        sig: 信号编号，表示收到的系统信号
        how: 关闭方式，表示如何关闭worker
        **kwargs: 其他关键字参数，Celery信号系统传递的额外信息
    """
    log.warning(f"Worker收到关闭信号: sig={sig}, how={how}")

    try:
        # 获取当前worker名称和进程ID
        worker_name = socket.gethostname()
        pid = os.getpid()

        # 获取当前进程状态
        process_status = process_health_monitor.get_process_status(worker_name, pid)
        if process_status and process_status.get("current_task"):
            task_id = process_status.get("current_task")

            log.warning(f"Worker关闭，恢复任务状态: worker={worker_name}:{pid}, task_id={task_id}")

            # 获取任务信息
            task_info = task_manager.get_task_status(task_id)
            if task_info and task_info.get("status") == "running":
                # 将任务状态重置为pending
                task_manager.update_task_status(
                    task_id,
                    "pending",
                    error=f"Worker关闭（sig={sig}, how={how}），任务将重新分发"
                )

                # 将任务重新加入用户队列
                user_id = task_info.get("user_id")
                if user_id:
                    task_data = task_manager.get_task_data(task_id)
                    if task_data:
                        task_manager.add_task_to_user_queue(user_id, task_id, task_data)
                        log.info(f"任务已重新加入队列: task_id={task_id}, user_id={user_id}")
                    else:
                        log.error(f"无法获取任务数据，无法恢复任务: task_id={task_id}")
                else:
                    log.error(f"无法获取用户ID，无法恢复任务: task_id={task_id}")
    except Exception as e:
        log.error(f"处理worker关闭信号时出错: {e}", exc_info=True)

