"""
健康监控服务：监控进程心跳和任务超时，处理挂起进程
"""
import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from celery_mq.celery_app import celery_app
from celery_mq.task_manager import task_manager
from core.process_health_monitor import process_health_monitor, parse_iso_time
from config.config import my_config, ENV
from utils.log_utils import logger as log


class HealthMonitorService:
    """健康监控服务"""
    
    def __init__(self):
        """初始化监控服务"""
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 从配置中获取监控参数
        health_config = my_config.get("process_health", {})
        self.heartbeat_interval = health_config.get("heartbeat_interval", 10)
        self.check_interval = health_config.get("check_interval", 30)
        self.heartbeat_timeout = health_config.get("heartbeat_timeout", 60)
        self.task_timeout = health_config.get("task_timeout", 1800)  # 30分钟
        self.max_restart_count = health_config.get("max_restart_count", 2)
        
        log.info(f"健康监控服务初始化完成: "
                f"heartbeat_interval={self.heartbeat_interval}s, "
                f"check_interval={self.check_interval}s, "
                f"heartbeat_timeout={self.heartbeat_timeout}s, "
                f"task_timeout={self.task_timeout}s, "
                f"max_restart_count={self.max_restart_count}")
    
    def check_heartbeats(self) -> List[Dict[str, Any]]:
        """
        检查所有进程的心跳，返回超时的进程列表
        
        Returns:
            超时进程列表，每个元素包含 worker_name, pid, last_heartbeat
        """
        hung_processes = []
        current_time = time.time()
        
        try:
            # 获取所有已注册的进程
            processes = process_health_monitor.get_all_processes()
            
            for process_id in processes:
                try:
                    parts = process_id.split(":", 1)
                    if len(parts) != 2:
                        continue
                    
                    worker_name, pid_str = parts
                    pid = int(pid_str)
                    
                    # 获取进程状态
                    status = process_health_monitor.get_process_status(worker_name, pid)
                    if not status:
                        continue
                    
                    # 检查心跳是否超时
                    last_heartbeat_iso = status.get("heartbeat")
                    if not last_heartbeat_iso:
                        continue
                    
                    # 将ISO格式时间转换为时间戳进行比较
                    last_heartbeat_ts = parse_iso_time(last_heartbeat_iso)
                    if last_heartbeat_ts is None:
                        continue
                    
                    time_since_heartbeat = current_time - last_heartbeat_ts
                    
                    if time_since_heartbeat > self.heartbeat_timeout:
                        # 只检查运行中的进程
                        if status.get("status") == "running":
                            hung_processes.append({
                                "worker_name": worker_name,
                                "pid": pid,
                                "last_heartbeat": last_heartbeat_iso,
                                "time_since_heartbeat": time_since_heartbeat,
                                "current_task": status.get("current_task"),
                                "restart_count": status.get("restart_count", 0),
                            })
                            log.warning(f"检测到进程心跳超时: {worker_name}:{pid}, "
                                      f"超时时间={time_since_heartbeat:.1f}秒")
                
                except (ValueError, KeyError) as e:
                    log.error(f"检查进程心跳时出错: {process_id}, error={e}")
                    continue
        
        except Exception as e:
            log.error(f"检查心跳时出错: {e}", exc_info=True)
        
        return hung_processes
    
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
                    parts = process_id.split(":", 1)
                    if len(parts) != 2:
                        continue
                    
                    worker_name, pid_str = parts
                    pid = int(pid_str)
                    
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
    
    def handle_hung_process(self, hung_process: Dict[str, Any]) -> bool:
        """
        处理挂起的进程
        
        Args:
            hung_process: 挂起进程信息
            
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
                if current_task:
                    self.reassign_task(current_task)
                return True
            else:
                log.error(f"重启worker失败: {worker_name}:{pid}")
                return False
        
        except Exception as e:
            log.error(f"处理挂起进程失败: {worker_name}:{pid}, error={e}", exc_info=True)
            return False
    
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
    
    def handle_timeout_task(self, timeout_task: Dict[str, Any]) -> bool:
        """
        处理超时任务
        
        Args:
            timeout_task: 超时任务信息
            
        Returns:
            是否处理成功
        """
        task_id = timeout_task["task_id"]
        worker_name = timeout_task["worker_name"]
        pid = timeout_task["pid"]
        
        try:
            log.error(f"处理超时任务: task_id={task_id}, worker={worker_name}:{pid}")
            
            # 更新任务状态为失败
            error_msg = f"任务执行超时: 执行时间超过{self.task_timeout}秒"
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
            
            return True
        
        except Exception as e:
            log.error(f"处理超时任务失败: task_id={task_id}, error={e}", exc_info=True)
            return False
    
    def monitor_loop(self):
        """监控循环"""
        log.info("健康监控循环开始")
        
        while self.running:
            try:
                # 检查心跳
                hung_processes = self.check_heartbeats()
                for hung_process in hung_processes:
                    self.handle_hung_process(hung_process)
                
                # 检查任务超时
                timeout_tasks = self.check_task_timeouts()
                for timeout_task in timeout_tasks:
                    self.handle_timeout_task(timeout_task)
                
                # 等待指定时间
                time.sleep(self.check_interval)
            
            except Exception as e:
                log.error(f"监控循环出错: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def start(self):
        """启动监控服务"""
        if self.running:
            log.warning("健康监控服务已在运行")
            return
        
        log.info("启动健康监控服务...")
        self.running = True
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(
            target=self.monitor_loop,
            name="HealthMonitorThread",
            daemon=True
        )
        self.monitor_thread.start()
        
        log.info("健康监控服务已启动")
    
    def stop(self):
        """停止监控服务"""
        if not self.running:
            return
        
        log.info("停止健康监控服务...")
        self.running = False
        
        # 等待监控线程结束
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        log.info("健康监控服务已停止")


# 全局健康监控服务实例
health_monitor_service = HealthMonitorService()

