"""
健康监控服务：协调心跳检查、超时检查和进程状态管理

注意：监控服务只负责检测和标记异常状态，不执行重启操作。
任务异常由 Celery retries 机制自动处理。
当检测到进程丢失时，会将任务状态重置为pending以便重新分发。
"""
import threading
import time
from config.config import my_config, ENV
from core.health_monitor.heartbeat_checker import HeartbeatChecker
from core.health_monitor.timeout_checker import TaskTimeoutChecker
from core.health_monitor.restart_handler import ProcessRestartHandler
from core.health_monitor.reassignment_handler import TaskReassignmentHandler
from core.health_monitor.worker_checker import WorkerChecker
from core.health_monitor.metric_reporter import metric_reporter
from core.health_monitor.monitor import process_health_monitor
from celery_mq.task_manager import task_manager
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
        self.worker_check_interval = process_health_config.get("worker_check_interval", 30)  # Worker检查间隔（秒）
        self.min_healthy_workers = process_health_config.get("min_healthy_workers", 1)  # 最小健康worker数量
        
        # 初始化检查器和处理器
        self.heartbeat_checker = HeartbeatChecker(self.heartbeat_timeout)
        self.timeout_checker = TaskTimeoutChecker(self.task_timeout)
        self.restart_handler = ProcessRestartHandler(self.max_restart_count)
        self.reassignment_handler = TaskReassignmentHandler()
        self.worker_checker = WorkerChecker(self.min_healthy_workers)
        
        # 初始化监控指标上报服务
        self.metric_reporter = metric_reporter
        
        # 服务状态
        self.running = False
        self.heartbeat_thread = None
        self.timeout_thread = None
        self.recovery_thread = None
        self.worker_check_thread = None
        self._stop_event = threading.Event()
    
    def start(self):
        """启动健康监控服务"""
        if self.running:
            log.warning("健康监控服务已在运行中")
            return
        
        log.info("启动健康监控服务...")
        log.info(f"配置: heartbeat_timeout={self.heartbeat_timeout}s, "
                f"check_interval={self.check_interval}s, "
                f"task_timeout={self.task_timeout}s, "
                f"worker_check_interval={self.worker_check_interval}s, "
                f"min_healthy_workers={self.min_healthy_workers}")
        
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
        
        # 启动任务恢复检查线程
        self.recovery_thread = threading.Thread(
            target=self._recovery_check_loop,
            name="TaskRecoveryChecker",
            daemon=True
        )
        self.recovery_thread.start()
        
        # 启动Worker检查线程
        self.worker_check_thread = threading.Thread(
            target=self._worker_check_loop,
            name="WorkerChecker",
            daemon=True
        )
        self.worker_check_thread.start()
        
        # 启动监控指标上报服务
        self.metric_reporter.start()
        
        log.info("健康监控服务已启动")
    
    def stop(self):
        """停止健康监控服务"""
        if not self.running:
            return
        
        log.info("停止健康监控服务...")
        self.running = False
        self._stop_event.set()
        
        # 停止监控指标上报服务
        self.metric_reporter.stop()
        
        # 等待线程结束
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        if self.timeout_thread:
            self.timeout_thread.join(timeout=5)
        if self.recovery_thread:
            self.recovery_thread.join(timeout=5)
        if self.worker_check_thread:
            self.worker_check_thread.join(timeout=5)
        
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
                        # 获取进程当前任务
                        worker_name = hung_process.get("worker_name")
                        pid = hung_process.get("pid")
                        current_task_id = hung_process.get("current_task")
                        
                        # 如果进程有正在执行的任务，恢复任务状态
                        if current_task_id:
                            self._recover_task_from_lost_process(worker_name, pid, current_task_id)
                        
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
    
    def _recover_task_from_lost_process(self, worker_name: str, pid: int, task_id: str):
        """
        恢复因进程丢失而中断的任务
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            task_id: 任务ID
        """
        try:
            # 检查任务状态
            task_info = task_manager.get_task_status(task_id)
            if not task_info:
                log.warning(f"任务不存在，无法恢复: task_id={task_id}")
                return
            
            # 只恢复running状态的任务
            if task_info.get("status") != "running":
                log.debug(f"任务状态不是running，无需恢复: task_id={task_id}, status={task_info.get('status')}")
                return
            
            log.warning(
                f"检测到进程丢失，恢复任务状态: "
                f"worker={worker_name}:{pid}, task_id={task_id}"
            )
            
            # 将任务状态重置为pending
            task_manager.update_task_status(
                task_id,
                "pending",
                error=f"Worker进程丢失: {worker_name}:{pid}，任务将重新分发"
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
            log.error(f"恢复任务失败: worker={worker_name}:{pid}, task_id={task_id}, error={e}", exc_info=True)
    
    def _recovery_check_loop(self):
        """
        任务恢复检查循环：定期扫描所有running状态但进程已丢失的任务
        
        这个检查作为心跳检查的补充，用于处理心跳检查可能遗漏的情况
        """
        log.info("任务恢复检查线程已启动")
        
        # 从配置读取恢复检查间隔
        process_health_config = my_config.get("process_health", {})
        recovery_check_interval = process_health_config.get("recovery_check_interval", 300)  # 默认5分钟
        
        while self.running and not self._stop_event.is_set():
            try:
                # 获取所有活跃进程
                all_processes = process_health_monitor.get_all_processes()
                active_process_set = set()
                
                for process_str in all_processes:
                    try:
                        worker_name, pid_str = process_str.split(":")
                        pid = int(pid_str)
                        
                        # 检查进程是否还有心跳（通过获取进程状态）
                        process_status = process_health_monitor.get_process_status(worker_name, pid)
                        if process_status:
                            # 进程存在且有状态，添加到活跃进程集合
                            active_process_set.add(process_str)
                    except (ValueError, AttributeError) as e:
                        log.debug(f"解析进程ID失败: {process_str}, error={e}")
                        continue
                
                # 扫描所有进程，查找丢失进程的任务
                for process_str in all_processes:
                    try:
                        worker_name, pid_str = process_str.split(":")
                        pid = int(pid_str)
                        
                        # 如果进程不在活跃集合中，检查是否有未完成的任务
                        if process_str not in active_process_set:
                            process_status = process_health_monitor.get_process_status(worker_name, pid)
                            if process_status:
                                current_task_id = process_status.get("current_task")
                                if current_task_id:
                                    log.warning(
                                        f"恢复检查发现丢失进程的任务: "
                                        f"worker={worker_name}:{pid}, task_id={current_task_id}"
                                    )
                                    self._recover_task_from_lost_process(
                                        worker_name, pid, current_task_id
                                    )
                    except (ValueError, AttributeError) as e:
                        log.debug(f"处理进程时出错: {process_str}, error={e}")
                        continue
                
                # 等待下次检查
                self._stop_event.wait(timeout=recovery_check_interval)
                
            except Exception as e:
                log.error(f"任务恢复检查循环出错: {e}", exc_info=True)
                # 出错后等待1分钟再继续
                self._stop_event.wait(timeout=60)
        
        log.info("任务恢复检查线程已停止")
    
    def _worker_check_loop(self):
        """
        Worker检查循环：定期检查worker存活状态和数量
        
        检查内容：
        1. 使用Celery inspect API检查活跃worker
        2. 验证Redis中注册的进程是否真的存在
        3. 检查worker数量是否满足最小要求
        4. 清理已消失worker的Redis记录
        5. 恢复已消失worker正在执行的任务
        """
        log.info("Worker检查线程已启动")
        
        while self.running and not self._stop_event.is_set():
            try:
                # 检查worker状态
                check_result = self.worker_checker.check_workers()
                
                # 处理已消失的worker
                missing_workers = check_result.get("missing_workers", [])
                if missing_workers:
                    log.warning(f"检测到 {len(missing_workers)} 个已消失的worker")
                    
                    # 清理已消失worker的Redis记录
                    cleaned_count = self.worker_checker.cleanup_missing_workers(missing_workers)
                    log.info(f"已清理 {cleaned_count} 个已消失worker的Redis记录")
                    
                    # 恢复已消失worker正在执行的任务
                    for missing_worker in missing_workers:
                        if missing_worker.get("needs_recovery"):
                            worker_name = missing_worker.get("worker_name")
                            pid = missing_worker.get("pid")
                            current_task_id = missing_worker.get("current_task")
                            
                            if current_task_id:
                                self._recover_task_from_lost_process(
                                    worker_name, pid, current_task_id
                                )
                
                # 检查worker数量是否满足要求
                if not check_result.get("healthy", False):
                    active_count = check_result.get("active_worker_count", 0)
                    log.warning(
                        f"Worker数量不足: 当前={active_count}, "
                        f"最小要求={self.min_healthy_workers}。"
                        f"请检查worker是否正常运行，或由外部系统（如K8s）重启worker。"
                    )
                
                # 等待下次检查
                self._stop_event.wait(timeout=self.worker_check_interval)
                
            except Exception as e:
                log.error(f"Worker检查循环出错: {e}", exc_info=True)
                # 出错后等待一段时间再继续
                self._stop_event.wait(timeout=5)
        
        log.info("Worker检查线程已停止")


# 全局服务实例
health_monitor_service = HealthMonitorService()

