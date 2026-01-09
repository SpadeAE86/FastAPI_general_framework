"""
用户队列服务

负责用户任务队列操作，遵循单一职责原则 (SRP)。
从原 TaskManager 中提取队列管理逻辑。
"""
from typing import List
import redis
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
    ACTIVE_USERS_KEY: str = "active_users"
    VIP_USERS_KEY: str = "vip_users"
    
    def __init__(self, redis_client: redis.Redis):
        """
        初始化用户队列服务
        
        Args:
            redis_client: Redis 客户端实例
        """
        self.redis = redis_client
    
    def _get_queue_key(self, user_id: str) -> str:
        """获取用户队列键"""
        return f"pending:tasks:{user_id}"
    
    def add_task(self, user_id: str, task_id: str) -> None:
        """
        将任务添加到用户队列
        
        使用 LPUSH 将任务添加到队列头部（后进先出）
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
        """
        queue_key = self._get_queue_key(user_id)
        self.redis.lpush(queue_key, task_id)
        self.redis.expire(queue_key, self.QUEUE_TTL)
        
        # 标记用户为活跃状态
        self.mark_user_active(user_id)
        
        log.debug(f"任务添加到用户队列: user_id={user_id}, task_id={task_id}")
    
    def fetch_tasks(self, user_id: str, count: int = 1) -> List[str]:
        """
        从用户队列获取任务
        
        使用 RPOP 从队列尾部取出任务（先进先出）
        
        Args:
            user_id: 用户ID
            count: 获取数量
            
        Returns:
            任务ID列表
        """
        queue_key = self._get_queue_key(user_id)
        task_ids = []
        
        for _ in range(count):
            task_id = self.redis.rpop(queue_key)
            if task_id:
                task_ids.append(task_id)
            else:
                break
        
        # 如果队列为空，从活跃用户集合中移除
        queue_length = self.redis.llen(queue_key)
        if queue_length == 0:
            self.redis.srem(self.ACTIVE_USERS_KEY, user_id)
            log.info(f"用户 {user_id} 队列已空，从活跃用户集合中移除")
        
        return task_ids
    
    def remove_task(self, user_id: str, task_id: str) -> None:
        """
        从用户队列中移除指定任务
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
        """
        queue_key = self._get_queue_key(user_id)
        self.redis.lrem(queue_key, 0, task_id)
    
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
