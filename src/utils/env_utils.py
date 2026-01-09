"""
环境检测工具模块

提供 Worker 名称解析和环境检测功能，遵循 DRY 原则，
消除 HeartbeatChecker 和 WorkerChecker 中的重复代码。
"""
from typing import Optional, List
from config.config import ENV


# 支持的环境标识模式
ENV_PATTERNS: List[str] = ['_local', '_test', '_prod', '_dev', '_staging']


def extract_env_from_worker_name(worker_name: str) -> Optional[str]:
    """
    从 Worker 名称中提取环境标识
    
    支持的格式：
    - celery_local@hostname -> local
    - celery_test@hostname -> test
    - celery_prod@hostname -> prod
    - worker_name_local@hostname -> local
    
    Args:
        worker_name: Worker 名称，格式为 "worker_name_env@hostname" 或 "worker_name@hostname"
        
    Returns:
        环境标识（如 "local", "test", "prod"），如果未找到返回 None
        
    Example:
        >>> extract_env_from_worker_name("celery_local@myhost")
        'local'
        >>> extract_env_from_worker_name("celery@myhost")
        None
    """
    # 提取 @ 之前的部分
    name_part = worker_name.split("@")[0] if "@" in worker_name else worker_name
    
    # 检查是否包含环境标识
    for pattern in ENV_PATTERNS:
        if name_part.endswith(pattern):
            return pattern[1:]  # 去掉下划线前缀
    
    return None


def is_same_env(worker_name: str, current_env: Optional[str] = None) -> bool:
    """
    判断 Worker 是否属于指定环境
    
    Args:
        worker_name: Worker 名称（Celery 格式或 Redis 格式）
        current_env: 目标环境，默认使用配置中的 ENV
        
    Returns:
        如果 Worker 属于指定环境返回 True，否则返回 False
        
    Note:
        Worker 名称必须明确包含环境标识（如 _local, _test, _prod 等），
        如果没有环境标识，将返回 False，拒绝该 Worker。
        
    Example:
        >>> is_same_env("celery_local@myhost", "local")
        True
        >>> is_same_env("celery_prod@myhost", "local")
        False
    """
    if current_env is None:
        current_env = ENV
    
    # 从 Worker 名称提取环境
    worker_env = extract_env_from_worker_name(worker_name)
    
    # 如果 Worker 名称中没有环境标识，拒绝该 Worker
    if worker_env is None:
        return False
    
    # 比较环境是否匹配
    return worker_env == current_env


def extract_hostname_from_worker_name(worker_name: str) -> Optional[str]:
    """
    从 Celery Worker 名称中提取 hostname
    
    Args:
        worker_name: Celery Worker 名称，格式为 "worker_name@hostname"
        
    Returns:
        hostname 部分，如果格式不正确返回 None
        
    Example:
        >>> extract_hostname_from_worker_name("celery_local@myhost")
        'myhost'
        >>> extract_hostname_from_worker_name("celery_local")
        None
    """
    if "@" in worker_name:
        return worker_name.split("@", 1)[1]
    return None
