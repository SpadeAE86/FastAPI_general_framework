"""
进程健康检查服务：负责进程注册、心跳更新、状态管理
"""
import os
import time
import socket
from typing import Optional, Dict, Any, List
import redis
from config.config import my_config, ENV
from utils.log_utils import logger as log
from utils.redis_client import RedisClientFactory
from utils.time_utils import (
    get_shanghai_iso_time,
    parse_iso_time,
    convert_to_shanghai_iso_time
)


class ProcessHealthMonitor:
    """进程健康监控器"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        初始化进程健康监控器
        
        Args:
            redis_client: Redis 客户端（可选，用于依赖注入测试）
        """
        # 使用共享的 Redis 客户端工厂
        self.redis_client = redis_client or RedisClientFactory.get_client()
        log.info("ProcessHealthMonitor 初始化完成")
    
    def get_process_key_prefix(self, worker_name: str, pid: int) -> str:
        """
        获取进程Redis键前缀
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            Redis键前缀
        """
        return f"process:{worker_name}:{pid}"
    
    def register_process(self, worker_name: str, pid: int) -> bool:
        """
        注册进程到Redis
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            是否注册成功
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            current_iso_time = get_shanghai_iso_time()
            
            # 设置进程信息
            self.redis_client.set(f"{key_prefix}:heartbeat", current_iso_time, ex=120)
            self.redis_client.set(f"{key_prefix}:status", "idle", ex=86400)
            self.redis_client.set(f"{key_prefix}:start_time", current_iso_time, ex=86400)
            self.redis_client.set(f"{key_prefix}:restart_count", 0, ex=86400)
            
            # 添加到进程集合
            self.redis_client.sadd("processes:all", f"{worker_name}:{pid}")
            self.redis_client.expire("processes:all", 86400)
            
            log.info(f"进程注册成功: {worker_name}:{pid}")
            return True
        except Exception as e:
            log.error(f"注册进程失败: {worker_name}:{pid}, error={e}")
            return False
    
    def update_heartbeat(self, worker_name: str, pid: int) -> bool:
        """
        更新心跳时间戳
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            是否更新成功
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            current_iso_time = get_shanghai_iso_time()
            
            # 更新心跳时间，设置过期时间为120秒（心跳超时的2倍）
            self.redis_client.set(f"{key_prefix}:heartbeat", current_iso_time, ex=120)
            
            return True
        except Exception as e:
            log.error(f"更新心跳失败: {worker_name}:{pid}, error={e}")
            return False
    
    def update_task_assignment(self, worker_name: str, pid: int, task_id: str) -> bool:
        """
        更新任务分配信息
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            task_id: 任务ID
            
        Returns:
            是否更新成功
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            current_iso_time = get_shanghai_iso_time()
            
            # 更新进程状态和任务信息
            self.redis_client.set(f"{key_prefix}:status", "running", ex=86400)
            self.redis_client.set(f"{key_prefix}:current_task", task_id, ex=86400)
            self.redis_client.set(f"{key_prefix}:heartbeat", current_iso_time, ex=120)
            
            log.info(f"任务分配更新: {worker_name}:{pid}, task_id={task_id}")
            return True
        except Exception as e:
            log.error(f"更新任务分配失败: {worker_name}:{pid}, task_id={task_id}, error={e}")
            return False
    
    def clear_task_assignment(self, worker_name: str, pid: int) -> bool:
        """
        清除任务分配信息（任务完成或失败时调用）
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            是否清除成功
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            
            # 更新进程状态为空闲，清除当前任务
            self.redis_client.set(f"{key_prefix}:status", "idle", ex=86400)
            self.redis_client.delete(f"{key_prefix}:current_task")
            
            return True
        except Exception as e:
            log.error(f"清除任务分配失败: {worker_name}:{pid}, error={e}")
            return False
    
    def get_process_status(self, worker_name: str, pid: int) -> Optional[Dict[str, Any]]:
        """
        获取进程状态
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            进程状态信息字典，如果进程不存在返回None
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            
            # 检查进程是否存在
            heartbeat = self.redis_client.get(f"{key_prefix}:heartbeat")
            if heartbeat is None:
                return None
            
            # 获取所有进程信息
            status = self.redis_client.get(f"{key_prefix}:status") or "unknown"
            current_task = self.redis_client.get(f"{key_prefix}:current_task")
            start_time = self.redis_client.get(f"{key_prefix}:start_time")
            restart_count = self.redis_client.get(f"{key_prefix}:restart_count") or "0"
            last_restart_time = self.redis_client.get(f"{key_prefix}:last_restart_time")
            
            # 转换时间字段为上海时区的ISO格式
            heartbeat_iso = convert_to_shanghai_iso_time(heartbeat)
            start_time_iso = convert_to_shanghai_iso_time(start_time)
            last_restart_time_iso = convert_to_shanghai_iso_time(last_restart_time)
            
            return {
                "worker_name": worker_name,
                "pid": pid,
                "status": status,
                "current_task": current_task,
                "heartbeat": heartbeat_iso,  # 上海时区的ISO格式字符串
                "start_time": start_time_iso,  # 上海时区的ISO格式字符串
                "restart_count": int(restart_count),
                "last_restart_time": last_restart_time_iso,  # 上海时区的ISO格式字符串或None
            }
        except Exception as e:
            log.error(f"获取进程状态失败: {worker_name}:{pid}, error={e}")
            return None
    
    def get_all_processes(self) -> list:
        """
        获取所有已注册的进程列表
        
        Returns:
            进程标识列表，格式为 ["worker_name:pid", ...]
        """
        try:
            processes = self.redis_client.smembers("processes:all")
            return list(processes) if processes else []
        except Exception as e:
            log.error(f"获取所有进程失败: {e}")
            return []
    
    def mark_process_hung(self, worker_name: str, pid: int) -> bool:
        """
        标记进程为挂起状态
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            是否标记成功
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            self.redis_client.set(f"{key_prefix}:status", "hung", ex=86400)
            log.warning(f"进程标记为挂起: {worker_name}:{pid}")
            return True
        except Exception as e:
            log.error(f"标记进程挂起失败: {worker_name}:{pid}, error={e}")
            return False
    
    def increment_restart_count(self, worker_name: str, pid: int) -> int:
        """
        增加重启计数（原子操作）
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            新的重启计数
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            restart_count = self.redis_client.incr(f"{key_prefix}:restart_count")
            self.redis_client.expire(f"{key_prefix}:restart_count", 86400)
            
            # 记录最后重启时间
            restart_iso_time = get_shanghai_iso_time()
            self.redis_client.set(f"{key_prefix}:last_restart_time", restart_iso_time, ex=86400)
            
            log.info(f"进程重启计数增加: {worker_name}:{pid}, count={restart_count}")
            return restart_count
        except Exception as e:
            log.error(f"增加重启计数失败: {worker_name}:{pid}, error={e}")
            return 0
    
    def get_restart_count(self, worker_name: str, pid: int) -> int:
        """
        获取重启计数
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            重启计数
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            restart_count = self.redis_client.get(f"{key_prefix}:restart_count")
            return int(restart_count) if restart_count else 0
        except Exception as e:
            log.error(f"获取重启计数失败: {worker_name}:{pid}, error={e}")
            return 0
    
    def cleanup_process(self, worker_name: str, pid: int) -> bool:
        """
        清理进程信息（进程正常退出时调用）
        
        Args:
            worker_name: Worker名称
            pid: 进程ID
            
        Returns:
            是否清理成功
        """
        try:
            key_prefix = self.get_process_key_prefix(worker_name, pid)
            
            # 删除所有进程相关的键
            keys_to_delete = [
                f"{key_prefix}:heartbeat",
                f"{key_prefix}:status",
                f"{key_prefix}:current_task",
                f"{key_prefix}:start_time",
                f"{key_prefix}:restart_count",
                f"{key_prefix}:last_restart_time",
            ]
            
            for key in keys_to_delete:
                self.redis_client.delete(key)
            
            # 从进程集合中移除
            self.redis_client.srem("processes:all", f"{worker_name}:{pid}")
            
            log.info(f"进程信息清理完成: {worker_name}:{pid}")
            return True
        except Exception as e:
            log.error(f"清理进程信息失败: {worker_name}:{pid}, error={e}")
            return False


# 全局进程健康监控器实例
process_health_monitor = ProcessHealthMonitor()



