"""
任务重新分配处理器：负责任务状态标记和记录

注意：监控服务不再自动重新分配任务，任务重试由 Celery retries 机制处理。
此类主要用于标记和记录超时任务的状态。
"""
from celery_mq.task_manager import task_manager
from core.health_monitor.monitor import process_health_monitor
from utils.log_utils import logger as log
import time


class TaskReassignmentHandler:
    """任务重新分配处理器"""
    
    def reassign_task(self, task_id: str) -> bool:
        """
        重新分配任务到队列
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否重新分配成功
        """
        try:
            # 获取任务信息
            task_info = task_manager.get_task_status(task_id)
            if not task_info:
                log.warning(f"任务不存在，无法重新分配: task_id={task_id}")
                return False
            
            # 将任务状态重置为pending
            task_manager.update_task_status(task_id, "pending")
            
            # 将任务重新加入用户队列
            user_id = task_info.get("user_id")
            if user_id:
                task_data = task_manager.get_task_data(task_id)
                if task_data:
                    task_manager.add_task_to_user_queue(user_id, task_id, task_data)
                    log.info(f"任务已重新分配到队列: task_id={task_id}, user_id={user_id}")
                    return True
            
            log.warning(f"无法获取用户ID，任务重新分配失败: task_id={task_id}")
            return False
        
        except Exception as e:
            log.error(f"重新分配任务失败: task_id={task_id}, error={e}", exc_info=True)
            return False
    
    def handle_timeout_task(self, timeout_task: dict, task_timeout: int) -> bool:
        """
        处理超时任务（只标记，不重新分配）
        
        注意：不再重新分配任务，由 Celery retries 机制处理任务重试。
        监控服务只负责检测和标记超时状态。

        Args:
            timeout_task: 超时任务信息
            task_timeout: 任务超时时间（秒）

        Returns:
            是否处理成功
        """
        task_id = timeout_task["task_id"]
        worker_name = timeout_task["worker_name"]
        pid = timeout_task["pid"]

        try:
            log.error(f"检测到超时任务: task_id={task_id}, worker={worker_name}:{pid}, "
                     f"超时时间={task_timeout}秒")

            # 更新任务状态为失败
            error_msg = f"任务执行超时: 执行时间超过{task_timeout}秒"
            task_manager.update_task_status(
                task_id,
                "failed",
                error=error_msg,
                failed_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            )

            # 清除进程的任务分配
            process_health_monitor.clear_task_assignment(worker_name, pid)

            # 标记进程为可疑
            process_health_monitor.mark_process_hung(worker_name, pid)
            
            log.info(f"超时任务已标记为失败，任务重试将由 Celery retries 机制处理")

            return True

        except Exception as e:
            log.error(f"处理超时任务失败: task_id={task_id}, error={e}", exc_info=True)
            return False

