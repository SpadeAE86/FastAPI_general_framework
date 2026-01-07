"""
健康监控服务：协调心跳检查、超时检查和进程状态管理

注意：监控服务只负责检测和标记异常状态，不执行重启操作。
任务异常由 Celery retries 机制自动处理。
"""
import threading
import time
from config.config import my_config, ENV
from core.health_monitor.heartbeat_checker import HeartbeatChecker
from core.health_monitor.timeout_checker import TaskTimeoutChecker
from core.health_monitor.restart_handler import ProcessRestartHandler
from core.health_monitor.reassignment_handler import TaskReassignmentHandler
from utils.log_utils import logger as log


class HealthMonitorService:
    """健康监控服务"""
    
    def __init__(self):
        """初始化健康监控服务"""
        # 从配置中获取参数
        process_health_config = my_config.get("process_health", {})
        
        self.heartbeat_timeout = process_health_config.get("heartbeat_timeout", 60)  # 心跳超时时间（秒）
        self.check_interval = process_health_config.get("check_interval", 30)  # 监控检查间隔（秒）
        self.task_timeout = process_health_config.get("task_timeout", 1800)  # 任务超时时间（秒，默认30分钟）
        self.max_restart_count = process_health_config.get("max_restart_count", 2)  # 最大重启次数（仅用于记录，不再用于控制重启）
        
        # 初始化检查器和处理器
        self.heartbeat_checker = HeartbeatChecker(self.heartbeat_timeout)
        self.timeout_checker = TaskTimeoutChecker(self.task_timeout)
        self.restart_handler = ProcessRestartHandler(self.max_restart_count)
        self.reassignment_handler = TaskReassignmentHandler()
        
        # 服务状态
        self.running = False
        self.heartbeat_thread = None
        self.timeout_thread = None
        self._stop_event = threading.Event()
    
    def start(self):
        """启动健康监控服务"""
        if self.running:
            log.warning("健康监控服务已在运行中")
            return
        
        log.info("启动健康监控服务...")
        log.info(f"配置: heartbeat_timeout={self.heartbeat_timeout}s, "
                f"check_interval={self.check_interval}s, "
                f"task_timeout={self.task_timeout}s")
        
        self.running = True
        self._stop_event.clear()
        
        # 启动心跳检查线程
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_check_loop,
            name="HeartbeatChecker",
            daemon=True
        )
        self.heartbeat_thread.start()
        
        # 启动超时检查线程
        self.timeout_thread = threading.Thread(
            target=self._timeout_check_loop,
            name="TaskTimeoutChecker",
            daemon=True
        )
        self.timeout_thread.start()
        
        log.info("健康监控服务已启动")
    
    def stop(self):
        """停止健康监控服务"""
        if not self.running:
            return
        
        log.info("停止健康监控服务...")
        self.running = False
        self._stop_event.set()
        
        # 等待线程结束
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        if self.timeout_thread:
            self.timeout_thread.join(timeout=5)
        
        log.info("健康监控服务已停止")
    
    def _heartbeat_check_loop(self):
        """心跳检查循环"""
        log.info("心跳检查线程已启动")
        
        while self.running and not self._stop_event.is_set():
            try:
                # 检查心跳
                hung_processes = self.heartbeat_checker.check_heartbeats()
                
                # 处理挂起的进程（只标记，不重启）
                for hung_process in hung_processes:
                    try:
                        self.restart_handler.handle_hung_process(
                            hung_process,
                            reassignment_handler=None  # 不再重新分配任务
                        )
                    except Exception as e:
                        log.error(f"处理挂起进程失败: {hung_process}, error={e}", exc_info=True)
                
                # 等待下次检查
                self._stop_event.wait(timeout=self.check_interval)
                
            except Exception as e:
                log.error(f"心跳检查循环出错: {e}", exc_info=True)
                # 出错后等待一段时间再继续
                self._stop_event.wait(timeout=5)
        
        log.info("心跳检查线程已停止")
    
    def _timeout_check_loop(self):
        """超时检查循环"""
        log.info("超时检查线程已启动")
        
        while self.running and not self._stop_event.is_set():
            try:
                # 检查任务超时
                timeout_tasks = self.timeout_checker.check_task_timeouts()
                
                # 处理超时任务（只标记，不重新分配）
                for timeout_task in timeout_tasks:
                    try:
                        self.reassignment_handler.handle_timeout_task(
                            timeout_task,
                            self.task_timeout
                        )
                    except Exception as e:
                        log.error(f"处理超时任务失败: {timeout_task}, error={e}", exc_info=True)
                
                # 等待下次检查
                self._stop_event.wait(timeout=self.check_interval)
                
            except Exception as e:
                log.error(f"超时检查循环出错: {e}", exc_info=True)
                # 出错后等待一段时间再继续
                self._stop_event.wait(timeout=5)
        
        log.info("超时检查线程已停止")


# 全局服务实例
health_monitor_service = HealthMonitorService()

