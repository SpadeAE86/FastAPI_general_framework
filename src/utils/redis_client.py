"""
Redis 客户端工厂模块

提供统一的 Redis 连接管理，遵循 DRY 原则，避免多处重复初始化 Redis 连接。
"""
from typing import Optional
import redis
from config.config import my_config, ENV
from utils.log_utils import logger as log


class RedisClientFactory:
    """
    Redis 客户端工厂（单例模式）
    
    使用工厂模式提供统一的 Redis 客户端实例，确保整个应用使用同一个连接。
    
    Example:
        >>> client = RedisClientFactory.get_client()
        >>> client.ping()
        True
    """
    _instance: Optional[redis.Redis] = None
    _initialized: bool = False
    
    @classmethod
    def get_client(cls) -> redis.Redis:
        """
        获取 Redis 客户端实例
        
        Returns:
            redis.Redis: Redis 客户端实例
            
        Raises:
            redis.ConnectionError: 无法连接到 Redis 服务器
        """
        if cls._instance is None:
            cls._instance = cls._create_client()
            cls._initialized = True
        return cls._instance
    
    @classmethod
    def _create_client(cls) -> redis.Redis:
        """
        创建 Redis 客户端实例
        
        Returns:
            redis.Redis: 新创建的 Redis 客户端实例
        """
        redis_config = my_config.get("redis", {}).get(ENV, {})
        
        client = redis.Redis(
            host=redis_config.get("host", "127.0.0.1"),
            port=redis_config.get("port", 6379),
            db=redis_config.get("database", 0),
            password=redis_config.get("password"),
            decode_responses=True
        )
        
        # 测试连接
        try:
            client.ping()
            log.info(f"Redis 连接成功: {redis_config.get('host', '127.0.0.1')}:{redis_config.get('port', 6379)}")
        except redis.ConnectionError as e:
            log.error(f"Redis 连接失败: {e}")
            raise
        
        return client
    
    @classmethod
    def reset(cls) -> None:
        """
        重置客户端实例（主要用于测试）
        """
        if cls._instance is not None:
            try:
                cls._instance.close()
            except Exception:
                pass
        cls._instance = None
        cls._initialized = False


def get_redis_client() -> redis.Redis:
    """
    获取 Redis 客户端的便捷函数
    
    Returns:
        redis.Redis: Redis 客户端实例
    """
    return RedisClientFactory.get_client()
