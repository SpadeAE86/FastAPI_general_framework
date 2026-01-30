"""
任务管理层：负责任务的创建、去重、状态管理和队列操作

重构说明：使用组合模式 (Composition) 代替大类，遵循单一职责原则 (SRP)。
将 429 行代码拆分为多个专门的服务类，同时保持向后兼容。
"""
import time
import uuid
from typing import Optional, Dict, List, Any
import redis
from celery_mq.protocols import TaskManagerProtocol
from celery_mq.task_repository import TaskRepository
from celery_mq.task_hash_service import TaskHashService
from celery_mq.user_queue_service import UserQueueService
from utils.redis_client import RedisClientFactory
from utils.time_utils import (
    get_shanghai_iso_time,
    parse_iso_time,
    convert_to_shanghai_iso_time
)
from utils.log_utils import logger as log


class TaskManager(TaskManagerProtocol):
    """
    任务管理器 - 门面类 (Facade Pattern)
    
    协调各子服务完成任务管理功能，对外提供统一接口，保持向后兼容。
    
    组合的服务：
    - TaskRepository: 任务 CRUD 操作
    - TaskHashService: 任务去重
    - UserQueueService: 用户队列管理
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        repository: Optional[TaskRepository] = None,
        hash_service: Optional[TaskHashService] = None,
        queue_service: Optional[UserQueueService] = None
    ):
        """
        初始化任务管理器
        
        支持依赖注入以便于测试。如果不提供依赖，将使用默认实现。
        
        Args:
            redis_client: Redis 客户端（可选，用于向后兼容）
            repository: 任务存储库（可选）
            hash_service: 任务去重服务（可选）
            queue_service: 用户队列服务（可选）
        """
        # 使用提供的 Redis 客户端或从工厂获取
        self.redis_client = redis_client or RedisClientFactory.get_client()
        
        # 初始化子服务（支持依赖注入）
        self._repository = repository or TaskRepository(self.redis_client)
        self._hash_service = hash_service or TaskHashService(self.redis_client)
        self._queue_service = queue_service or UserQueueService(self.redis_client)
        
        log.info("TaskManager 初始化完成")
    
    # ==================== 核心任务操作 ====================
    
    def create_task(self, user_id: str, task_data: Dict[str, Any]) -> str:
        """
        创建任务，计算 task_hash，检查重复，写入 Redis 队列
        
        Args:
            user_id: 用户ID
            task_data: 任务数据字典
            
        Returns:
            task_id: 任务ID
        """
        # 计算任务哈希
        task_hash = self._hash_service.calculate_hash(task_data)
        
        # 检查是否重复
        existing_task_id = self._hash_service.check_duplicate(task_hash)
        if existing_task_id:
            log.info(f"任务重复，返回已有任务ID: {existing_task_id}")
            return existing_task_id
        
        # 生成新的任务ID
        task_id = f"task_{uuid.uuid4().hex[:16]}"
        
        # 注册任务哈希映射
        self._hash_service.register_hash(task_hash, task_id)
        
        # 保存任务详细信息
        task_info = {
            "task_id": task_id,
            "user_id": user_id,
            "status": "pending",
            "created_at": get_shanghai_iso_time(),
            "task_hash": task_hash,
            "result": "null" # 初始化为空
        }
        self._repository.save_task(task_id, task_info)
        
        # 保存任务数据（用于 worker 执行）
        self._repository.save_task_data(task_id, task_data)
        
        # 将任务添加到用户队列
        self.add_task_to_user_queue(user_id, task_id, task_data)
        
        log.info(f"任务创建成功: task_id={task_id}, user_id={user_id}")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息字典，如果任务不存在返回 None
        """
        task_info = self._repository.get_task(task_id)
        
        if not task_info:
            return None
        
        # 获取开始时间（如果存在）
        start_time_iso = self._repository.get_start_time(task_id)
        if start_time_iso:
            task_info['start_time'] = convert_to_shanghai_iso_time(start_time_iso)
        
        # 获取子任务列表
        subtasks = self._repository.get_subtasks(task_id)
        task_info["subtasks"] = subtasks
        
        return task_info
    
    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务数据（用于 worker 执行）
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务数据字典，如果任务不存在返回 None
        """
        return self._repository.get_task_data(task_id)
    
    def update_task_status(self, task_id: str, status: str, **kwargs: Any) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态（pending/dispatched/running/completed/failed）
            **kwargs: 其他要更新的字段
        """
        self._repository.update_task(task_id, status=status, **kwargs)
        
        # 如果任务完成或失败，删除开始时间记录
        if status in ["completed", "failed"]:
            self._repository.clear_start_time(task_id)
    
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务及其相关数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 删除是否成功
        """
        # 获取任务信息
        task_info = self._repository.get_task(task_id)
        if not task_info:
            return False
        
        user_id = task_info.get("user_id")
        task_hash = task_info.get("task_hash")
        
        # 删除任务哈希映射
        if task_hash:
            self._hash_service.delete_hash(task_hash)
        
        # 从用户队列中移除任务
        if user_id:
            self._queue_service.remove_task(user_id, task_id)
        
        # 删除任务本身
        return self._repository.delete_task(task_id)
    
    def get_task_subtasks(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取子任务列表
        
        Args:
            task_id: 任务ID
            
        Returns:
            子任务列表
        """
        return self._repository.get_subtasks(task_id)
    
    # ==================== 任务时间管理 ====================
    
    def record_task_start_time(self, task_id: str) -> None:
        """
        记录任务开始时间（ISO 格式，上海时区）
        
        Args:
            task_id: 任务ID
        """
        self._repository.record_start_time(task_id)
    
    def get_task_start_time(self, task_id: str) -> Optional[float]:
        """
        获取任务开始时间（转换为时间戳用于比较）
        
        Args:
            task_id: 任务ID
            
        Returns:
            开始时间戳，如果不存在返回 None
        """
        start_time_iso = self._repository.get_start_time(task_id)
        if not start_time_iso:
            return None
        return parse_iso_time(start_time_iso)
    
    def get_task_start_time_iso(self, task_id: str) -> Optional[str]:
        """
        获取任务开始时间（ISO 格式字符串）
        
        Args:
            task_id: 任务ID
            
        Returns:
            ISO 格式时间字符串，如果不存在返回 None
        """
        return self._repository.get_start_time(task_id)
    
    def check_task_timeout(self, task_id: str, timeout_seconds: int = 1800) -> bool:
        """
        检查任务是否超时
        
        Args:
            task_id: 任务ID
            timeout_seconds: 超时阈值（秒），默认 30 分钟
            
        Returns:
            是否超时
        """
        start_time = self.get_task_start_time(task_id)
        if not start_time:
            return False
        
        elapsed_time = time.time() - start_time
        return elapsed_time > timeout_seconds
    
    # ==================== 用户队列操作 ====================
    
    def add_task_to_user_queue(
        self, user_id: str, task_id: str, task_data: Dict[str, Any]
    ) -> None:
        """
        将任务添加到用户队列
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
            task_data: 任务数据（保留参数以保持向后兼容）
        """
        self._queue_service.add_task(user_id, task_id)
    
    def fetch_tasks_from_user_queue(self, user_id: str, count: int = 1) -> List[str]:
        """
        从用户队列中取出指定数量的任务
        
        Args:
            user_id: 用户ID
            count: 要取出的任务数量
            
        Returns:
            任务ID列表
        """
        return self._queue_service.fetch_tasks(user_id, count)
    
    def mark_user_active(self, user_id: str) -> None:
        """
        标记用户为活跃状态
        
        Args:
            user_id: 用户ID
        """
        self._queue_service.mark_user_active(user_id)
    
    def get_active_users(self) -> List[str]:
        """
        获取所有活跃用户ID列表
        
        Returns:
            活跃用户ID列表
        """
        return self._queue_service.get_active_users()
    
    def get_vip_users(self) -> List[str]:
        """
        获取VIP用户ID列表
        
        Returns:
            VIP用户ID列表
        """
        return self._queue_service.get_vip_users()
    
    def add_vip_user(self, user_id: str) -> None:
        """
        添加VIP用户
        
        Args:
            user_id: 用户ID
        """
        self._queue_service.add_vip_user(user_id)
    
    def remove_vip_user(self, user_id: str) -> None:
        """
        移除VIP用户
        
        Args:
            user_id: 用户ID
        """
        self._queue_service.remove_vip_user(user_id)
    
    # ==================== 向后兼容方法 ====================
    
    def calculate_task_hash(self, task_data: Dict[str, Any]) -> str:
        """
        计算任务 hash（向后兼容）
        
        Args:
            task_data: 任务数据字典
            
        Returns:
            task_hash: MD5 哈希值
        """
        return self._hash_service.calculate_hash(task_data)
    
    def check_task_duplicate(self, task_hash: str) -> Optional[str]:
        """
        检查任务是否重复（向后兼容）
        
        Args:
            task_hash: 任务 hash 值
            
        Returns:
            如果重复，返回已有 task_id；否则返回 None
        """
        return self._hash_service.check_duplicate(task_hash)


# 全局任务管理器实例（向后兼容）
task_manager = TaskManager()
