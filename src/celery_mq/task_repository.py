"""
任务存储库服务

负责任务的 CRUD 操作，遵循单一职责原则 (SRP)。
从原 TaskManager 中提取任务持久化逻辑。
"""
import json
from typing import Optional, Dict, List, Any
import redis
from celery_mq.protocols import TaskRepositoryProtocol
from utils.time_utils import (
    get_shanghai_iso_time,
    convert_to_shanghai_iso_time
)
from utils.log_utils import logger as log


class TaskRepository(TaskRepositoryProtocol):
    """
    任务存储库
    
    负责任务信息的持久化操作，包括：
    - 任务元信息的存储和查询
    - 任务执行数据的存储和查询
    - 子任务的管理
    """
    
    # 任务键过期时间（7天）
    TASK_TTL: int = 86400 * 7
    
    def __init__(self, redis_client: redis.Redis):
        """
        初始化任务存储库
        
        Args:
            redis_client: Redis 客户端实例
        """
        self.redis = redis_client
    
    def _get_task_key(self, task_id: str) -> str:
        """获取任务键"""
        return f"task:{task_id}"
    
    def _get_task_data_key(self, task_id: str) -> str:
        """获取任务数据键"""
        return f"task:{task_id}:data"
    
    def _get_subtasks_key(self, task_id: str) -> str:
        """获取子任务列表键"""
        return f"task:{task_id}:subtasks"
    
    def _get_start_time_key(self, task_id: str) -> str:
        """获取任务开始时间键"""
        return f"task:{task_id}:start_time"
    
    def save_task(self, task_id: str, task_info: Dict[str, Any]) -> None:
        """
        保存任务信息
        
        Args:
            task_id: 任务ID
            task_info: 任务信息字典
        """
        task_key = self._get_task_key(task_id)
        self.redis.hset(task_key, mapping=task_info)
        self.redis.expire(task_key, self.TASK_TTL)
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典，如果不存在返回 None
        """
        task_key = self._get_task_key(task_id)
        task_info = self.redis.hgetall(task_key)
        
        if not task_info:
            return None
        
        # 转换时间字段为上海时区的 ISO 格式
        time_fields = ['created_at', 'updated_at', 'started_at', 'completed_at', 'failed_at']
        for field in time_fields:
            if field in task_info:
                task_info[field] = convert_to_shanghai_iso_time(task_info[field])

        # 反序列化 result 字段
        if 'result' in task_info and task_info['result'] and task_info['result'] != "null":
            try:
                task_info['result'] = json.loads(task_info['result'])
            except json.JSONDecodeError:
                log.warning(f"Failed to decode result for task {task_id}: {task_info['result']}")
        
        return task_info
    
    def update_task(self, task_id: str, **fields: Any) -> None:
        """
        更新任务字段
        
        Args:
            task_id: 任务ID
            **fields: 要更新的字段
        """
        task_key = self._get_task_key(task_id)
        update_data = {"updated_at": get_shanghai_iso_time()}
        
        # 序列化复杂类型
        for k, v in fields.items():
            if isinstance(v, (dict, list)):
                update_data[k] = json.dumps(v, ensure_ascii=False)
            elif v is None:
                update_data[k] = "null" # Redis doesn't store None/null natively in hash
            else:
                update_data[k] = v
                
        self.redis.hset(task_key, mapping=update_data)
    
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务及其相关数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否删除成功
        """
        task_key = self._get_task_key(task_id)
        task_info = self.redis.hgetall(task_key)
        
        if not task_info:
            return False
        
        # 删除任务数据
        task_data_key = self._get_task_data_key(task_id)
        self.redis.delete(task_data_key)
        
        # 删除子任务
        subtasks_key = self._get_subtasks_key(task_id)
        subtask_ids = self.redis.lrange(subtasks_key, 0, -1)
        for subtask_id in subtask_ids:
            subtask_key = f"subtask:{subtask_id}"
            self.redis.delete(subtask_key)
        self.redis.delete(subtasks_key)
        
        # 删除开始时间
        start_time_key = self._get_start_time_key(task_id)
        self.redis.delete(start_time_key)
        
        # 删除任务本身
        self.redis.delete(task_key)
        
        log.info(f"任务删除成功: task_id={task_id}")
        return True
    
    def save_task_data(self, task_id: str, task_data: Dict[str, Any]) -> None:
        """
        保存任务执行数据
        
        Args:
            task_id: 任务ID
            task_data: 任务执行数据
        """
        task_data_key = self._get_task_data_key(task_id)
        self.redis.set(
            task_data_key,
            json.dumps(task_data, ensure_ascii=False),
            ex=self.TASK_TTL
        )
    
    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务执行数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务数据字典，如果不存在返回 None
        """
        task_data_key = self._get_task_data_key(task_id)
        task_data_json = self.redis.get(task_data_key)
        
        if not task_data_json:
            return None
        
        return json.loads(task_data_json)
    
    def get_subtasks(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取子任务列表
        
        Args:
            task_id: 任务ID
            
        Returns:
            子任务列表
        """
        subtasks_key = self._get_subtasks_key(task_id)
        subtask_ids = self.redis.lrange(subtasks_key, 0, -1)
        
        subtasks = []
        for subtask_id in subtask_ids:
            subtask_key = f"subtask:{subtask_id}"
            subtask_info = self.redis.hgetall(subtask_key)
            if subtask_info:
                # 转换子任务中的时间字段
                time_fields = ['start_time', 'end_time', 'created_at', 'updated_at']
                for field in time_fields:
                    if field in subtask_info:
                        subtask_info[field] = convert_to_shanghai_iso_time(subtask_info[field])
                subtasks.append(subtask_info)
        
        return subtasks
    
    def record_start_time(self, task_id: str) -> None:
        """
        记录任务开始时间
        
        Args:
            task_id: 任务ID
        """
        start_time_key = self._get_start_time_key(task_id)
        self.redis.set(start_time_key, get_shanghai_iso_time(), ex=self.TASK_TTL)
    
    def get_start_time(self, task_id: str) -> Optional[str]:
        """
        获取任务开始时间（ISO 格式）
        
        Args:
            task_id: 任务ID
            
        Returns:
            ISO 格式时间字符串，如果不存在返回 None
        """
        start_time_key = self._get_start_time_key(task_id)
        return self.redis.get(start_time_key)
    
    def clear_start_time(self, task_id: str) -> None:
        """
        清除任务开始时间
        
        Args:
            task_id: 任务ID
        """
        start_time_key = self._get_start_time_key(task_id)
        self.redis.delete(start_time_key)
