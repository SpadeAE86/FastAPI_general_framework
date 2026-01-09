"""
心跳检查器：负责检查进程心跳是否超时
"""
import os
import socket
import time
from typing import List, Dict, Any, Optional
from core.health_monitor.monitor import process_health_monitor
from utils.time_utils import parse_iso_time
from utils.process_utils import parse_process_id
from utils.env_utils import extract_env_from_worker_name, is_same_env
from utils.log_utils import logger as log
from config.config import ENV


class HeartbeatChecker:
    """心跳检查器"""
    
    def __init__(self, heartbeat_timeout: int):
        """
        初始化心跳检查器
        
        Args:
            heartbeat_timeout: 心跳超时时间（秒）
        """
        self.heartbeat_timeout = heartbeat_timeout
        # 获取当前机器的主机名
        self.local_hostname = socket.gethostname()
        # 获取当前环境
        self.current_env = ENV
    
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
                    # 解析进程ID
                    parsed = parse_process_id(process_id)
                    if parsed is None:
                        continue
                    
                    worker_name, pid = parsed
                    
                    # 检查worker是否属于当前环境
                    if not is_same_env(worker_name, self.current_env):
                        log.debug(f"跳过不同环境的worker心跳检查: {worker_name} (当前环境: {self.current_env})")
                        continue
                    
                    # 获取进程状态
                    status = process_health_monitor.get_process_status(worker_name, pid)
                    if not status:
                        continue
                    
                    # 首先检查进程是否真的存在（仅对本地worker进行进程存活验证）
                    process_exists = self._check_process_exists(pid, worker_name)
                    is_local = worker_name == self.local_hostname
                    
                    if not process_exists:
                        # 本地进程不存在，立即标记为丢失（不等待心跳超时）
                        if status.get("status") == "running":
                            hung_processes.append({
                                "worker_name": worker_name,
                                "pid": pid,
                                "last_heartbeat": status.get("heartbeat"),
                                "time_since_heartbeat": None,  # 进程不存在，无法计算时间
                                "current_task": status.get("current_task"),
                                "restart_count": status.get("restart_count", 0),
                                "reason": "进程不存在（本地）" if is_local else "不在Celery活跃列表中"
                            })
                            log.warning(
                                f"检测到进程不存在（立即标记为丢失）: {worker_name}:{pid} "
                                f"(本地={is_local})"
                            )
                        continue
                    
                    # 进程存在，检查心跳是否超时
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
                                "reason": "心跳超时"
                            })
                            log.warning(f"检测到进程心跳超时: {worker_name}:{pid}, "
                                      f"超时时间={time_since_heartbeat:.1f}秒")
                
                except (ValueError, KeyError) as e:
                    log.error(f"检查进程心跳时出错: {process_id}, error={e}")
                    continue
        
        except Exception as e:
            log.error(f"检查心跳时出错: {e}", exc_info=True)
        
        return hung_processes
    
    def _check_process_exists(self, pid: int, worker_name: str) -> bool:
        """
        检查进程是否真的存在（仅适用于本地进程）
        
        Args:
            pid: 进程ID
            worker_name: Worker名称（hostname）
            
        Returns:
            如果进程存在返回True，否则返回False
        """
        # 只检查本地机器上的进程
        # Redis中存储的worker_name就是hostname
        if worker_name != self.local_hostname:
            # 远程worker，无法使用os.kill检查，返回True（假设存在）
            # 实际存在性由Celery inspect API判断
            return True
        
        try:
            # 使用os.kill(pid, 0)检查进程是否存在
            # 注意：os.kill只能检查本地机器上的进程
            os.kill(pid, 0)
            return True
        except OSError:
            # 进程不存在
            return False
        except Exception as e:
            log.warning(f"检查进程存在性时出错: pid={pid}, worker={worker_name}, error={e}")
            # 出错时保守处理，假设进程存在（避免误判）
            return True



