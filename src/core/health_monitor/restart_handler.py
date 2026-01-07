"""
进程重启处理器：负责进程重启逻辑
"""
from celery_mq.celery_app import celery_app
from celery_mq.task_manager import task_manager
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
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            是否重启成功
        """
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
                        log.warning(f"注意: worker {worker_name} 将被关闭，需要外部进程管理器（如systemd/supervisor/K8s）重启")
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
        
        Args:
            task_id: 任务ID
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            是否处理成功
        """
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
    
    def handle_hung_process(self, hung_process: dict, reassignment_handler) -> bool:
        """
        处理挂起的进程
        
        Args:
            hung_process: 挂起进程信息
            reassignment_handler: 任务重新分配处理器
            
        Returns:
            是否处理成功
        """
        worker_name = hung_process["worker_name"]
        pid = hung_process["pid"]
        restart_count = hung_process.get("restart_count", 0)
        current_task = hung_process.get("current_task")
        
        try:
            # 检查重启次数
            if restart_count >= self.max_restart_count:
                log.error(f"进程重启次数已达上限: {worker_name}:{pid}, "
                         f"restart_count={restart_count}, 停止任务")
                
                # 停止任务并标记失败
                if current_task:
                    self.stop_task_and_mark_failed(current_task, worker_name, pid)
                
                # 标记进程为错误状态
                process_health_monitor.mark_process_hung(worker_name, pid)
                return False
            
            # 标记进程为挂起
            process_health_monitor.mark_process_hung(worker_name, pid)
            
            # 增加重启计数
            new_restart_count = process_health_monitor.increment_restart_count(worker_name, pid)
            
            log.warning(f"准备重启挂起进程: {worker_name}:{pid}, "
                       f"restart_count={new_restart_count}/{self.max_restart_count}")
            
            # 重启worker
            if self.restart_worker(worker_name, pid):
                # 如果进程有当前任务，需要重新分配
                if current_task and reassignment_handler:
                    reassignment_handler.reassign_task(current_task)
                return True
            else:
                log.error(f"重启worker失败: {worker_name}:{pid}")
                return False
        
        except Exception as e:
            log.error(f"处理挂起进程失败: {worker_name}:{pid}, error={e}", exc_info=True)
            return False

