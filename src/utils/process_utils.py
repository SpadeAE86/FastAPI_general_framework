"""
进程工具函数：统一管理进程ID解析相关函数
"""
from typing import Optional, Tuple


def parse_process_id(process_id: str) -> Optional[Tuple[str, int]]:
    """
    解析进程ID字符串，提取worker名称和PID
    
    Args:
        process_id: 进程ID字符串，格式为 "worker_name:pid"
        
    Returns:
        如果解析成功，返回 (worker_name, pid) 元组；否则返回None
    """
    if not process_id:
        return None
    
    try:
        parts = process_id.split(":", 1)
        if len(parts) != 2:
            return None
        
        worker_name, pid_str = parts
        pid = int(pid_str)
        return (worker_name, pid)
    
    except (ValueError, AttributeError):
        return None

