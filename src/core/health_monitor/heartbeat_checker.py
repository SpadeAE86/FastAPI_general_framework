"""
心跳检查器：负责检查进程心跳是否超时
"""
import time
from typing import List, Dict, Any
from core.health_monitor.monitor import process_health_monitor
from utils.time_utils import parse_iso_time
from utils.process_utils import parse_process_id
from utils.log_utils import logger as log


class HeartbeatChecker:
    """心跳检查器"""
    
    def __init__(self, heartbeat_timeout: int):
        """
        初始化心跳检查器
        
        Args:
            heartbeat_timeout: 心跳超时时间（秒）
        """
        self.heartbeat_timeout = heartbeat_timeout
    
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

