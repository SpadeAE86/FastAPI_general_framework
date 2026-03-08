"""
时间工具函数：统一管理时间处理相关函数
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from utils.log_utils import logger as log

# 上海时区 (UTC+8)
SHANGHAI_TZ = timezone(timedelta(hours=8))


def get_shanghai_iso_time() -> str:
    """
    获取上海时区的ISO格式时间字符串
    
    Returns:
        ISO格式时间字符串，例如: "2024-01-01T12:00:00+08:00"
    """
    return datetime.now(SHANGHAI_TZ).isoformat()


def parse_iso_time(iso_time_str: str) -> Optional[float]:
    """
    将ISO格式时间字符串或时间戳字符串转换为时间戳（用于比较）
    兼容旧的时间戳格式和新的ISO格式
    
    Args:
        iso_time_str: ISO格式时间字符串或时间戳字符串
        
    Returns:
        时间戳（秒），如果解析失败返回None
    """
    if not iso_time_str:
        return None
    
    try:
        # 首先尝试作为时间戳解析（向后兼容旧格式）
        try:
            timestamp = float(iso_time_str)
            # 验证时间戳是否合理（1970年到2100年之间）
            if 0 <= timestamp <= 4102444800:
                return timestamp
        except (ValueError, TypeError):
            pass
        
        # 如果不是时间戳，尝试作为ISO格式解析
        # 处理Z后缀（UTC时间）
        time_str = iso_time_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(time_str)
        return dt.timestamp()
    
    except (ValueError, AttributeError) as e:
        log.error(f"解析时间失败: {iso_time_str}, error={e}")
        return None


def convert_to_shanghai_iso_time(time_value: Optional[str]) -> Optional[str]:
    """
    将时间戳或ISO时间字符串转换为上海时区的ISO格式时间
    
    Args:
        time_value: 时间戳字符串或ISO格式时间字符串
        
    Returns:
        上海时区的ISO格式时间字符串，例如: "2024-01-01T12:00:00+08:00"
        如果输入为None或空，返回None
    """
    if not time_value:
        return None
    
    try:
        # 首先尝试作为时间戳解析
        try:
            timestamp = float(time_value)
            # 验证时间戳是否合理（1970年到2100年之间）
            if 0 <= timestamp <= 4102444800:
                dt = datetime.fromtimestamp(timestamp, tz=SHANGHAI_TZ)
                return dt.isoformat()
        except (ValueError, TypeError, OSError):
            pass
        
        # 如果不是时间戳，尝试作为ISO格式解析
        # 处理Z后缀（UTC时间）
        time_str = time_value.replace('Z', '+00:00')
        dt = datetime.fromisoformat(time_str)
        
        # 如果时间没有时区信息，假设为UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        # 转换为上海时区
        dt_shanghai = dt.astimezone(SHANGHAI_TZ)
        return dt_shanghai.isoformat()
    
    except (ValueError, AttributeError) as e:
        log.warning(f"时间格式转换失败: {time_value}, error={e}")
        return time_value  # 如果转换失败，返回原值

