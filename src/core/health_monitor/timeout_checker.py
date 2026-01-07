"""
任务超时检查器：负责检查任务是否超时
"""
import time
from typing import List, Dict, Any
from celery_mq.task_manager import task_manager
from core.health_monitor.monitor import process_health_monitor
from utils.process_utils import parse_process_id
from utils.log_utils import logger as log


class TaskTimeoutChecker:
    """任务超时检查器"""
    
    def __init__(self, task_timeout: int):
        """
        初始化任务超时检查器
        
        Args:
            task_timeout: 任务超时时间（秒）
        """
        self.task_timeout = task_timeout
    
    def check_task_timeouts(self) -> List[Dict[str, Any]]:
        """
        检查所有运行中的任务是否超时
        
        Returns:
            超时任务列表
        """
        timeout_tasks = []
        current_time = time.time()
        
        try:
            # 获取所有运行中的进程
            processes = process_health_monitor.get_all_processes()
            
            for process_id in processes:
                try:
                    # 解析进程ID
                    parsed = parse_process_id(process_id)
                    if parsed is None:
                        continue
                    
                    worker_name, pid = parsed
                    
                    # 获取进程状态
                    status = process_health_monitor.get_process_status(worker_name, pid)
                    if not status or status.get("status") != "running":
                        continue
                    
                    task_id = status.get("current_task")
                    if not task_id:
                        continue
                    
                    # 检查任务开始时间（从任务管理器获取）
                    start_time = task_manager.get_task_start_time(task_id)
                    if not start_time:
                        continue
                    
                    task_duration = current_time - start_time
                    
                    if task_duration > self.task_timeout:
                        timeout_tasks.append({
                            "task_id": task_id,
                            "worker_name": worker_name,
                            "pid": pid,
                            "duration": task_duration,
                        })
                        log.warning(f"检测到任务超时: task_id={task_id}, "
                                  f"worker={worker_name}:{pid}, "
                                  f"执行时间={task_duration:.1f}秒")
                
                except (ValueError, KeyError) as e:
                    log.error(f"检查任务超时时出错: {process_id}, error={e}")
                    continue
        
        except Exception as e:
            log.error(f"检查任务超时时出错: {e}", exc_info=True)
        
        return timeout_tasks



