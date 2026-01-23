"""
进程重启处理器：负责进程状态标记和记录

注意：监控服务不再自动执行重启操作，任务异常由 Celery retries 机制处理。
此类主要用于标记和记录挂起进程的状态，以及提供手动重启功能（供 API 使用）。
"""


from core.health_monitor.monitor import process_health_monitor
from utils.log_utils import logger as log
import time


class ProcessRestartHandler:
    """进程重启处理器"""

    def __init__(self, max_restart_count: int):
        """
        初始化进程重启处理器

        Args:
            max_restart_count: 最大重启次数
        """
        self.max_restart_count = max_restart_count

    def restart_worker(self, worker_name: str, pid: int) -> bool:
        """
        使用Celery control API重启worker
        
        首先尝试使用pool_restart方法重启worker进程池（适用于prefork或threads pool），
        如果不可用则尝试使用shutdown命令关闭worker（需要外部进程管理器重启）。

        Args:
            worker_name: Worker名称，用于标识要重启的worker节点
            pid: 进程ID，用于日志记录（实际重启操作针对整个worker节点）

        Returns:
            bool: 如果重启命令发送成功返回True，否则返回False
        """
        from celery_mq.celery_app import celery_app
        try:
            control = celery_app.control

            # 方法1: 尝试使用pool_restart（需要prefork或threads pool）
            try:
                result = control.pool_restart(destination=[worker_name])
                log.info(f"使用pool_restart重启worker: {worker_name}, result={result}")
                return True
            except ValueError as e:
                if "Pool restarts not enabled" in str(e) or "not enabled" in str(e).lower():
                    log.warning(f"pool_restart不可用: {worker_name}, 尝试使用shutdown命令")

                    # 方法2: 使用shutdown命令（会关闭整个worker，需要外部进程管理器重启）
                    try:
                        result = control.shutdown(destination=[worker_name])
                        log.warning(f"发送shutdown命令到worker: {worker_name}, result={result}")
                        log.warning(
                            f"注意: worker {worker_name} 将被关闭，需要外部进程管理器（如systemd/supervisor/K8s）重启")
                        return True
                    except Exception as shutdown_error:
                        log.error(f"shutdown命令也失败: {worker_name}, error={shutdown_error}")
                        return False
                else:
                    # 其他ValueError，重新抛出
                    raise

        except Exception as e:
            log.error(f"重启worker失败: {worker_name}:{pid}, error={e}", exc_info=True)
            return False

    def stop_task_and_mark_failed(self, task_id: str, worker_name: str, pid: int) -> bool:
        """
        停止任务并标记为失败
        
        将任务状态更新为failed，清除进程的任务分配信息。
        用于处理进程挂起且重启次数已达上限的情况。

        Args:
            task_id: 任务ID，用于标识要停止的任务
            worker_name: Worker名称，用于日志记录
            pid: 进程ID，用于日志记录和清除任务分配

        Returns:
            bool: 如果处理成功返回True，否则返回False
        """
        from celery_mq.task_manager import task_manager
        try:
            log.error(f"停止任务并标记失败: task_id={task_id}, worker={worker_name}:{pid}")

            # 更新任务状态为失败
            error_msg = f"Worker进程挂起且重启次数已达上限: {worker_name}:{pid}"
            task_manager.update_task_status(
                task_id,
                "failed",
                error=error_msg,
                failed_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            )

            # 清除进程的任务分配
            process_health_monitor.clear_task_assignment(worker_name, pid)

            return True

        except Exception as e:
            log.error(f"停止任务失败: task_id={task_id}, error={e}", exc_info=True)
            return False

    def handle_hung_process(self, hung_process: dict, reassignment_handler=None) -> bool:
        """
        处理挂起的进程（只标记，不重启）
        
        标记进程为挂起状态，如果重启次数已达上限则标记相关任务为失败。
        注意：不再执行重启操作，由Celery retries机制处理任务重试。
        监控服务只负责检测和标记异常状态，不执行重启或任务重新分配。

        Args:
            hung_process: 挂起进程信息字典，包含worker_name、pid、restart_count、current_task等字段
            reassignment_handler: 任务重新分配处理器（已废弃，不再使用，保留参数以保持向后兼容）

        Returns:
            bool: 如果处理成功返回True，否则返回False
        """
        worker_name = hung_process["worker_name"]
        pid = hung_process["pid"]
        restart_count = hung_process.get("restart_count", 0)
        current_task = hung_process.get("current_task")

        try:
            # 标记进程为挂起
            process_health_monitor.mark_process_hung(worker_name, pid)
            
            # 检查重启次数（仅用于记录，不再用于控制重启）
            if restart_count >= self.max_restart_count:
                log.error(f"进程挂起且重启次数已达上限: {worker_name}:{pid}, "
                          f"restart_count={restart_count}, 标记任务失败")
                
                # 如果进程有当前任务，标记任务失败
                # 注意：不再重新分配任务，由 Celery retries 机制处理
                if current_task:
                    self.stop_task_and_mark_failed(current_task, worker_name, pid)
                
                # 标记进程为错误状态
                process_health_monitor.mark_process_hung(worker_name, pid)
                return True
            
            # 记录挂起进程信息（不执行重启）
            log.warning(f"检测到挂起进程: {worker_name}:{pid}, "
                       f"restart_count={restart_count}/{self.max_restart_count}, "
                       f"current_task={current_task}")
            log.info(f"挂起进程已标记，任务重试将由 Celery retries 机制处理")
            
            return True

        except Exception as e:
            log.error(f"处理挂起进程失败: {worker_name}:{pid}, error={e}", exc_info=True)
            return False

