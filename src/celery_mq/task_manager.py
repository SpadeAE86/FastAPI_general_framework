"""
任务管理层：负责任务的创建、去重、状态管理和队列操作
"""
import json
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
import redis
from config.config import my_config, ENV
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


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        """初始化Redis连接"""
        redis_config = my_config.get("redis", {}).get(ENV, {})
        self.redis_client = redis.Redis(
            host=redis_config.get("host", "127.0.0.1"),
            port=redis_config.get("port", 6379),
            db=redis_config.get("database", 0),
            password=redis_config.get("password"),
            decode_responses=True
        )
        # 测试连接
        try:
            self.redis_client.ping()
            log.info("Redis连接成功")
        except Exception as e:
            log.error(f"Redis连接失败: {e}")
            raise
    
    def calculate_task_hash(self, task_data: Dict[str, Any]) -> str:
        """
        计算任务hash（整个请求体MD5）
        
        Args:
            task_data: 任务数据字典
            
        Returns:
            task_hash: MD5哈希值
        """
        # 将任务数据序列化为JSON字符串，确保键排序一致
        task_json = json.dumps(task_data, sort_keys=True, ensure_ascii=False)
        # 计算MD5
        task_hash = hashlib.md5(task_json.encode('utf-8')).hexdigest()
        return task_hash
    
    def check_task_duplicate(self, task_hash: str) -> Optional[str]:
        """
        检查任务是否重复
        
        Args:
            task_hash: 任务hash值
            
        Returns:
            如果重复，返回已有task_id；否则返回None
        """
        hash_key = f"task_hash:{task_hash}"
        existing_task_id = self.redis_client.get(hash_key)
        return existing_task_id
    
    def create_task(self, user_id: str, task_data: Dict[str, Any]) -> str:
        """
        创建任务，计算task_hash，检查重复，写入Redis队列
        
        Args:
            user_id: 用户ID
            task_data: 任务数据字典
            
        Returns:
            task_id: 任务ID
        """
        # 计算任务hash
        task_hash = self.calculate_task_hash(task_data)
        
        # 检查是否重复
        existing_task_id = self.check_task_duplicate(task_hash)
        if existing_task_id:
            log.info(f"任务重复，返回已有任务ID: {existing_task_id}")
            return existing_task_id
        
        # 生成新的任务ID
        task_id = f"task_{uuid.uuid4().hex[:16]}"
        
        # 保存任务hash映射
        hash_key = f"task_hash:{task_hash}"
        self.redis_client.set(hash_key, task_id, ex=30)  # 30秒过期
        
        # 保存任务详细信息
        task_info = {
            "task_id": task_id,
            "user_id": user_id,
            "status": "pending",
            "created_at": get_shanghai_iso_time(),
            "task_hash": task_hash
        }
        task_key = f"task:{task_id}"
        self.redis_client.hset(task_key, mapping=task_info)
        self.redis_client.expire(task_key, 86400 * 7)  # 7天过期
        
        # 保存任务数据（用于worker执行）
        task_data_key = f"task:{task_id}:data"
        self.redis_client.set(task_data_key, json.dumps(task_data, ensure_ascii=False), ex=86400 * 7)
        
        # 将任务添加到用户队列
        self.add_task_to_user_queue(user_id, task_id, task_data)
        
        log.info(f"任务创建成功: task_id={task_id}, user_id={user_id}")
        return task_id
    
    def add_task_to_user_queue(self, user_id: str, task_id: str, task_data: Dict[str, Any]):
        """
        将任务添加到用户队列
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
            task_data: 任务数据
        """
        queue_key = f"pending:tasks:{user_id}"
        # 使用LPUSH将任务添加到队列头部
        self.redis_client.lpush(queue_key, task_id)
        self.redis_client.expire(queue_key, 86400 * 7)  # 7天过期
        
        # 标记用户为活跃状态
        self.mark_user_active(user_id)
    
    def mark_user_active(self, user_id: str):
        """
        标记用户为活跃状态
        
        Args:
            user_id: 用户ID
        """
        active_users_key = "active_users"
        self.redis_client.sadd(active_users_key, user_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息字典，如果任务不存在返回None
        """
        task_key = f"task:{task_id}"
        task_info = self.redis_client.hgetall(task_key)
        
        if not task_info:
            return None
        
        # 转换时间字段为上海时区的ISO格式
        if 'created_at' in task_info:
            task_info['created_at'] = convert_to_shanghai_iso_time(task_info['created_at'])
        if 'updated_at' in task_info:
            task_info['updated_at'] = convert_to_shanghai_iso_time(task_info['updated_at'])
        if 'started_at' in task_info:
            task_info['started_at'] = convert_to_shanghai_iso_time(task_info['started_at'])
        
        # 获取开始时间（如果存在）
        start_time_iso = self.get_task_start_time_iso(task_id)
        if start_time_iso:
            task_info['start_time'] = convert_to_shanghai_iso_time(start_time_iso)
        
        # 获取子任务列表
        subtasks = self.get_task_subtasks(task_id)
        task_info["subtasks"] = subtasks
        
        return task_info
    
    def get_task_subtasks(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取子任务列表
        
        Args:
            task_id: 任务ID
            
        Returns:
            子任务列表
        """
        subtasks_key = f"task:{task_id}:subtasks"
        subtask_ids = self.redis_client.lrange(subtasks_key, 0, -1)
        
        subtasks = []
        for subtask_id in subtask_ids:
            subtask_key = f"subtask:{subtask_id}"
            subtask_info = self.redis_client.hgetall(subtask_key)
            if subtask_info:
                # 转换子任务中的时间字段为上海时区的ISO格式
                if 'start_time' in subtask_info:
                    subtask_info['start_time'] = convert_to_shanghai_iso_time(subtask_info['start_time'])
                if 'end_time' in subtask_info:
                    subtask_info['end_time'] = convert_to_shanghai_iso_time(subtask_info['end_time'])
                if 'created_at' in subtask_info:
                    subtask_info['created_at'] = convert_to_shanghai_iso_time(subtask_info['created_at'])
                if 'updated_at' in subtask_info:
                    subtask_info['updated_at'] = convert_to_shanghai_iso_time(subtask_info['updated_at'])
                subtasks.append(subtask_info)
        
        return subtasks
    
    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务数据（用于worker执行）
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务数据字典，如果任务不存在返回None
        """
        task_data_key = f"task:{task_id}:data"
        task_data_json = self.redis_client.get(task_data_key)
        
        if not task_data_json:
            return None
        
        return json.loads(task_data_json)
    
    def record_task_start_time(self, task_id: str):
        """
        记录任务开始时间（ISO格式，上海时区）
        
        Args:
            task_id: 任务ID
        """
        task_start_key = f"task:{task_id}:start_time"
        start_iso_time = get_shanghai_iso_time()
        self.redis_client.set(task_start_key, start_iso_time, ex=86400 * 7)  # 7天过期
    
    def get_task_start_time(self, task_id: str) -> Optional[float]:
        """
        获取任务开始时间（转换为时间戳用于比较）
        
        Args:
            task_id: 任务ID
            
        Returns:
            开始时间戳，如果不存在返回None
        """
        task_start_key = f"task:{task_id}:start_time"
        start_time_iso = self.redis_client.get(task_start_key)
        if not start_time_iso:
            return None
        return parse_iso_time(start_time_iso)
    
    def get_task_start_time_iso(self, task_id: str) -> Optional[str]:
        """
        获取任务开始时间（ISO格式字符串）
        
        Args:
            task_id: 任务ID
            
        Returns:
            ISO格式时间字符串，如果不存在返回None
        """
        task_start_key = f"task:{task_id}:start_time"
        return self.redis_client.get(task_start_key)
    
    def check_task_timeout(self, task_id: str, timeout_seconds: int = 1800) -> bool:
        """
        检查任务是否超时
        
        Args:
            task_id: 任务ID
            timeout_seconds: 超时阈值（秒），默认30分钟
            
        Returns:
            是否超时
        """
        start_time = self.get_task_start_time(task_id)
        if not start_time:
            return False
        
        import time
        elapsed_time = time.time() - start_time
        return elapsed_time > timeout_seconds
    
    def update_task_status(self, task_id: str, status: str, **kwargs):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态（pending/dispatched/running/completed/failed）
            **kwargs: 其他要更新的字段
        """
        task_key = f"task:{task_id}"
        update_data = {"status": status, "updated_at": get_shanghai_iso_time()}
        update_data.update(kwargs)
        self.redis_client.hset(task_key, mapping=update_data)
        
        # 如果任务完成或失败，删除开始时间记录
        if status in ["completed", "failed"]:
            task_start_key = f"task:{task_id}:start_time"
            self.redis_client.delete(task_start_key)
    
    def fetch_tasks_from_user_queue(self, user_id: str, count: int = 1) -> List[str]:
        """
        从用户队列中取出指定数量的任务
        
        Args:
            user_id: 用户ID
            count: 要取出的任务数量
            
        Returns:
            任务ID列表
        """
        queue_key = f"pending:tasks:{user_id}"
        task_ids = []
        
        for _ in range(count):
            task_id = self.redis_client.rpop(queue_key)
            if task_id:
                task_ids.append(task_id)
            else:
                break
        
        # 如果队列为空，从活跃用户集合中移除
        queue_length = self.redis_client.llen(queue_key)
        if queue_length == 0:
            active_users_key = "active_users"
            self.redis_client.srem(active_users_key, user_id)
            log.info(f"用户 {user_id} 队列已空，从活跃用户集合中移除")
        
        return task_ids
    
    def get_active_users(self) -> List[str]:
        """
        获取所有活跃用户ID列表
        
        Returns:
            活跃用户ID列表
        """
        active_users_key = "active_users"
        return list(self.redis_client.smembers(active_users_key))
    
    def get_vip_users(self) -> List[str]:
        """
        获取VIP用户ID列表
        
        Returns:
            VIP用户ID列表
        """
        vip_users_key = "vip_users"
        return list(self.redis_client.smembers(vip_users_key))
    
    def add_vip_user(self, user_id: str):
        """
        添加VIP用户
        
        Args:
            user_id: 用户ID
        """
        vip_users_key = "vip_users"
        self.redis_client.sadd(vip_users_key, user_id)
    
    def remove_vip_user(self, user_id: str):
        """
        移除VIP用户
        
        Args:
            user_id: 用户ID
        """
        vip_users_key = "vip_users"
        self.redis_client.srem(vip_users_key, user_id)

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务及其相关数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 删除是否成功
        """
        task_key = f"task:{task_id}"
        
        # 1. 获取任务信息
        task_info = self.redis_client.hgetall(task_key)
        if not task_info:
            return False
            
        user_id = task_info.get("user_id")
        task_hash = task_info.get("task_hash")
        
        # 2. 删除任务hash映射
        if task_hash:
            hash_key = f"task_hash:{task_hash}"
            self.redis_client.delete(hash_key)
            
        # 3. 删除任务数据
        task_data_key = f"task:{task_id}:data"
        self.redis_client.delete(task_data_key)
        
        # 4. 删除子任务
        subtasks_key = f"task:{task_id}:subtasks"
        subtask_ids = self.redis_client.lrange(subtasks_key, 0, -1)
        for subtask_id in subtask_ids:
            subtask_key = f"subtask:{subtask_id}"
            self.redis_client.delete(subtask_key)
        self.redis_client.delete(subtasks_key)
        
        # 5. 删除任务本身
        self.redis_client.delete(task_key)
        
        # 6. 从用户队列中移除任务
        if user_id:
            queue_key = f"pending:tasks:{user_id}"
            self.redis_client.lrem(queue_key, 0, task_id)
            
        log.info(f"任务删除成功: task_id={task_id}")
        return True


# 全局任务管理器实例
task_manager = TaskManager()

