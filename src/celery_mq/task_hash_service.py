"""
任务去重服务

负责任务哈希计算和重复检测，遵循单一职责原则 (SRP)。
从原 TaskManager 中提取去重逻辑。
"""
import json
import hashlib
from typing import Optional, Dict, Any
import redis
from celery_mq.protocols import TaskHashServiceProtocol
from config.config import ENV
from utils.log_utils import logger as log


class TaskHashService(TaskHashServiceProtocol):
    """
    任务去重服务
    
    负责：
    - 计算任务数据的 MD5 哈希值
    - 检测重复任务
    - 注册任务哈希映射
    """
    
    # 默认哈希过期时间（30秒）
    DEFAULT_HASH_TTL: int = 30
    
    def __init__(self, redis_client: redis.Redis):
        """
        初始化任务去重服务
        
        Args:
            redis_client: Redis 客户端实例
        """
        self.redis = redis_client
    
    def _get_hash_key(self, task_hash: str) -> str:
        """获取哈希映射键"""
        return f"{ENV}:task_hash:{task_hash}"
    
    def calculate_hash(self, task_data: Dict[str, Any]) -> str:
        """
        计算任务哈希值（整个请求体 MD5）
        
        Args:
            task_data: 任务数据字典
            
        Returns:
            MD5 哈希值
        """
        # 将任务数据序列化为 JSON 字符串，确保键排序一致
        task_json = json.dumps(task_data, sort_keys=True, ensure_ascii=False)
        # 计算 MD5
        task_hash = hashlib.md5(task_json.encode('utf-8')).hexdigest()
        return task_hash
    
    def check_duplicate(self, task_hash: str) -> Optional[str]:
        """
        检查任务是否重复
        
        Args:
            task_hash: 任务哈希值
            
        Returns:
            如果重复返回已有任务ID，否则返回 None
        """
        hash_key = self._get_hash_key(task_hash)
        existing_task_id = self.redis.get(hash_key)
        
        if existing_task_id:
            log.debug(f"检测到重复任务: hash={task_hash}, existing_task_id={existing_task_id}")
        
        return existing_task_id
    
    def register_hash(self, task_hash: str, task_id: str, ttl: int = None) -> None:
        """
        注册任务哈希映射
        
        Args:
            task_hash: 任务哈希值
            task_id: 任务ID
            ttl: 过期时间（秒），默认 30 秒
        """
        if ttl is None:
            ttl = self.DEFAULT_HASH_TTL
        
        hash_key = self._get_hash_key(task_hash)
        self.redis.set(hash_key, task_id, ex=ttl)
        log.debug(f"注册任务哈希: hash={task_hash}, task_id={task_id}, ttl={ttl}s")
    
    def delete_hash(self, task_hash: str) -> None:
        """
        删除任务哈希映射
        
        Args:
            task_hash: 任务哈希值
        """
        hash_key = self._get_hash_key(task_hash)
        self.redis.delete(hash_key)
