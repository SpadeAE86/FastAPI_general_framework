"""
健康监控服务：监控进程心跳和任务超时，处理挂起进程
作为协调者，组合各个专门的处理器
"""
import time
import threading
from typing import List, Dict, Any, Optional
from config.config import my_config, ENV
from utils.log_utils import logger as log
from core.health_monitor.heartbeat_checker import HeartbeatChecker
from core.health_monitor.timeout_checker import TaskTimeoutChecker
from core.health_monitor.restart_handler import ProcessRestartHandler
from core.health_monitor.reassignment_handler import TaskReassignmentHandler


class HealthMonitorService:
    """健康监控服务 - 协调者模式"""
    
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
        
        # 创建各个专门的处理器
        self.heartbeat_checker = HeartbeatChecker(self.heartbeat_timeout)
        self.timeout_checker = TaskTimeoutChecker(self.task_timeout)
        self.restart_handler = ProcessRestartHandler(self.max_restart_count)
        self.reassignment_handler = TaskReassignmentHandler()
        
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
        return self.heartbeat_checker.check_heartbeats()
    
    def check_task_timeouts(self) -> List[Dict[str, Any]]:
        """
        检查所有运行中的任务是否超时
        
        Returns:
            超时任务列表
        """
        return self.timeout_checker.check_task_timeouts()
    
    def handle_hung_process(self, hung_process: Dict[str, Any]) -> bool:
        """
        处理挂起的进程
        
        Args:
            hung_process: 挂起进程信息
            
        Returns:
            是否处理成功
        """
        return self.restart_handler.handle_hung_process(
            hung_process, 
            self.reassignment_handler
        )
    
    def handle_timeout_task(self, timeout_task: Dict[str, Any]) -> bool:
        """
        处理超时任务
        
        Args:
            timeout_task: 超时任务信息
            
        Returns:
            是否处理成功
        """
        return self.reassignment_handler.handle_timeout_task(
            timeout_task, 
            self.task_timeout
        )
    
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

