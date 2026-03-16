"""
用户队列服务

负责用户任务队列操作，遵循单一职责原则 (SRP)。
从原 TaskManager 中提取队列管理逻辑。
"""
from typing import List
import redis
from config.config import ENV
from celery_mq.protocols import UserQueueServiceProtocol
from utils.log_utils import logger as log


class UserQueueService(UserQueueServiceProtocol):
    """
    用户队列服务
    
    负责：
    - 管理用户的待处理任务队列
    - 跟踪活跃用户
    - 管理 VIP 用户列表
    """
    
    # 队列过期时间（7天）
    QUEUE_TTL: int = 86400 * 7
    
    # Redis 键名
    ACTIVE_USERS_KEY: str = f"{ENV}:active_users"
    VIP_USERS_KEY: str = f"{ENV}:vip_users"
    
    def __init__(self, redis_client: redis.Redis):
        """
        初始化用户队列服务
        
        Args:
            redis_client: Redis 客户端实例
        """
        self.redis = redis_client
    
    def _get_queue_key(self, user_id: str, task_type: str = "mix") -> str:
        """获取用户任务类型队列键"""
        return f"{ENV}:pending:tasks:{user_id}:{task_type}"
    
    def _get_active_types_key(self, user_id: str) -> str:
        """获取用户当前活跃的任务类型集合 Key"""
        return f"{ENV}:user:active_types:{user_id}"
    
    def add_task(self, user_id: str, task_id: str, task_type: str = "mix") -> None:
        """
        将任务添加到用户特定类型的队列
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
            task_type: 任务类型
        """
        queue_key = self._get_queue_key(user_id, task_type)
        active_types_key = self._get_active_types_key(user_id)
        
        self.redis.lpush(queue_key, task_id)
        self.redis.expire(queue_key, self.QUEUE_TTL)
        
        # 记录该用户有此类任务
        self.redis.sadd(active_types_key, task_type)
        
        # 标记用户为活跃状态
        self.mark_user_active(user_id)
        
        log.info(f"任务已加入用户类型队列: user_id={user_id}, type={task_type}, task_id={task_id}")
    
    def fetch_tasks(self, user_id: str, count: int = 1, task_type: str = "mix") -> List[str]:
        """
        从用户指定类型的队列获取任务
        
        Args:
            user_id: 用户ID
            count: 获取数量
            task_type: 任务类型
            
        Returns:
            任务ID列表
        """
        queue_key = self._get_queue_key(user_id, task_type)
        task_ids = []
        
        for _ in range(count):
            task_id_bytes = self.redis.rpop(queue_key)
            if task_id_bytes:
                # 处理 bytes -> str
                if isinstance(task_id_bytes, bytes):
                    task_ids.append(task_id_bytes.decode('utf-8'))
                else:
                    task_ids.append(task_id_bytes)
            else:
                break
        
        # 如果队列为空，从本地记录的活跃类型中移除
        queue_length = self.redis.llen(queue_key)
        if queue_length == 0:
            self.redis.srem(self._get_active_types_key(user_id), task_type)
            log.info(f"用户 {user_id} 类型 {task_type} 队列已空")
            
        # 触发清理逻辑：如果没有活跃类型了，才真正移除活跃用户
        active_types = self.get_user_active_types(user_id)
        if not active_types:
            self.redis.srem(self.ACTIVE_USERS_KEY, user_id)
            self.redis.srem(self.VIP_USERS_KEY, user_id)
            log.info(f"用户 {user_id} 所有任务已空，标记为非活跃")
            
        return task_ids

    def get_user_active_types(self, user_id: str) -> List[str]:
        """获取用户当前有任务排队的所有类型"""
        active_types_key = self._get_active_types_key(user_id)
        types = self.redis.smembers(active_types_key)
        if not types:
            return []
        return [t.decode('utf-8') if isinstance(t, bytes) else t for t in types]
    
    def remove_task(self, user_id: str, task_id: str, task_type: str = "mix") -> None:
        """从用户队列中移除指定任务"""
        queue_key = self._get_queue_key(user_id, task_type)
        self.redis.lrem(queue_key, 0, task_id)
        
        # 如果删除后队列空了，更新活跃类型
        if self.redis.llen(queue_key) == 0:
            self.redis.srem(self._get_active_types_key(user_id), task_type)
    
    def get_active_users(self) -> List[str]:
        """
        获取所有活跃用户
        
        Returns:
            活跃用户ID列表
        """
        users = self.redis.smembers(self.ACTIVE_USERS_KEY)
        return list(users) if users else []
    
    def mark_user_active(self, user_id: str) -> None:
        """
        标记用户为活跃状态
        
        Args:
            user_id: 用户ID
        """
        self.redis.sadd(self.ACTIVE_USERS_KEY, user_id)
    
    def get_vip_users(self) -> List[str]:
        """
        获取VIP用户列表
        
        Returns:
            VIP用户ID列表
        """
        vip_users = self.redis.smembers(self.VIP_USERS_KEY)
        return list(vip_users) if vip_users else []
    
    def add_vip_user(self, user_id: str) -> None:
        """
        添加VIP用户
        
        Args:
            user_id: 用户ID
        """
        self.redis.sadd(self.VIP_USERS_KEY, user_id)
        log.info(f"添加VIP用户: {user_id}")
    
    def remove_vip_user(self, user_id: str) -> None:
        """
        移除VIP用户
        
        Args:
            user_id: 用户ID
        """
        self.redis.srem(self.VIP_USERS_KEY, user_id)
        log.info(f"移除VIP用户: {user_id}")
