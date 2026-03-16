"""
任务管理协议定义

定义任务管理相关的抽象接口，遵循依赖倒置原则 (DIP)，
使上层模块依赖抽象而非具体实现，提高代码可测试性。
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any


class TaskRepositoryProtocol(ABC):
    """
    任务存储库协议
    
    定义任务的 CRUD 操作接口。
    """
    
    @abstractmethod
    def save_task(self, task_id: str, task_info: Dict[str, Any]) -> None:
        """
        保存任务信息
        
        Args:
            task_id: 任务ID
            task_info: 任务信息字典
        """
        ...
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典，如果不存在返回 None
        """
        ...
    
    @abstractmethod
    def update_task(self, task_id: str, **fields: Any) -> None:
        """
        更新任务字段
        
        Args:
            task_id: 任务ID
            **fields: 要更新的字段
        """
        ...
    
    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否删除成功
        """
        ...
    
    @abstractmethod
    def save_task_data(self, task_id: str, task_data: Dict[str, Any]) -> None:
        """
        保存任务执行数据
        
        Args:
            task_id: 任务ID
            task_data: 任务执行数据
        """
        ...
    
    @abstractmethod
    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务执行数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务数据字典，如果不存在返回 None
        """
        ...


class TaskHashServiceProtocol(ABC):
    """
    任务去重服务协议
    
    定义任务哈希计算和重复检测接口。
    """
    
    @abstractmethod
    def calculate_hash(self, task_data: Dict[str, Any]) -> str:
        """
        计算任务哈希值
        
        Args:
            task_data: 任务数据字典
            
        Returns:
            MD5 哈希值
        """
        ...
    
    @abstractmethod
    def check_duplicate(self, task_hash: str) -> Optional[str]:
        """
        检查任务是否重复
        
        Args:
            task_hash: 任务哈希值
            
        Returns:
            如果重复返回已有任务ID，否则返回 None
        """
        ...
    
    @abstractmethod
    def register_hash(self, task_hash: str, task_id: str, ttl: int) -> None:
        """
        注册任务哈希
        
        Args:
            task_hash: 任务哈希值
            task_id: 任务ID
            ttl: 过期时间（秒）
        """
        ...


class UserQueueServiceProtocol(ABC):
    """
    用户队列服务协议
    
    定义用户任务队列操作接口。
    """
    
    @abstractmethod
    def add_task(self, user_id: str, task_id: str, task_type: str = "mix") -> None:
        """
        将任务添加到用户特定类型的队列
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
            task_type: 任务类型
        """
        ...
    
    @abstractmethod
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
        ...
    
    @abstractmethod
    def get_user_active_types(self, user_id: str) -> List[str]:
        """
        获取用户当前有任务排队的所有类型
        
        Args:
            user_id: 用户ID
            
        Returns:
            任务类型列表
        """
        ...
    
    @abstractmethod
    def get_active_users(self) -> List[str]:
        """
        获取所有活跃用户
        
        Returns:
            活跃用户ID列表
        """
        ...
    
    @abstractmethod
    def mark_user_active(self, user_id: str) -> None:
        """
        标记用户为活跃状态
        
        Args:
            user_id: 用户ID
        """
        ...
    
    @abstractmethod
    def get_vip_users(self) -> List[str]:
        """
        获取VIP用户列表
        
        Returns:
            VIP用户ID列表
        """
        ...


class TaskManagerProtocol(ABC):
    """
    任务管理器协议 - 门面接口
    
    定义任务管理的高层接口，用于 API 层依赖注入。
    """
    
    @abstractmethod
    def create_task(self, user_id: str, task_data: Dict[str, Any]) -> str:
        """
        创建任务
        
        Args:
            user_id: 用户ID
            task_data: 任务数据
            
        Returns:
            任务ID
        """
        ...
    
    @abstractmethod
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息，如果不存在返回 None
        """
        ...
    
    @abstractmethod
    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务执行数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务数据，如果不存在返回 None
        """
        ...
    
    @abstractmethod
    def update_task_status(self, task_id: str, status: str, **kwargs: Any) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            **kwargs: 其他要更新的字段
        """
        ...
    
    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否删除成功
        """
        ...
    
    @abstractmethod
    def get_task_subtasks(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取子任务列表
        
        Args:
            task_id: 任务ID
            
        Returns:
            子任务列表
        """
        ...
    
    @abstractmethod
    def record_task_start_time(self, task_id: str) -> None:
        """
        记录任务开始时间
        
        Args:
            task_id: 任务ID
        """
        ...
    
    @abstractmethod
    def add_task_to_user_queue(
        self, user_id: str, task_id: str, task_data: Dict[str, Any]
    ) -> None:
        """
        将任务添加到用户队列
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
            task_data: 任务数据（由此提取 task_type）
        """
        ...
    
    @abstractmethod
    def fetch_tasks_from_user_queue(self, user_id: str, count: int = 1, task_type: str = "mix") -> List[str]:
        """
        从用户队列获取任务
        
        Args:
            user_id: 用户ID
            count: 获取数量
            task_type: 任务类型
            
        Returns:
            任务ID列表
        """
        ...

    @abstractmethod
    def get_user_active_task_types(self, user_id: str) -> List[str]:
        """
        获取用户活跃的任务类型
        
        Args:
            user_id: 用户ID
            
        Returns:
            活跃任务类型列表
        """
        ...


class ProcessHealthMonitorProtocol(ABC):
    """
    进程健康监控器协议
    
    定义进程健康检查的接口。
    """
    
    @abstractmethod
    def register_process(self, worker_name: str, pid: int) -> bool:
        """注册进程"""
        ...
    
    @abstractmethod
    def update_heartbeat(self, worker_name: str, pid: int) -> bool:
        """更新心跳"""
        ...
    
    @abstractmethod
    def get_process_status(self, worker_name: str, pid: int) -> Optional[Dict[str, Any]]:
        """获取进程状态"""
        ...
    
    @abstractmethod
    def get_all_processes(self) -> List[str]:
        """获取所有进程列表"""
        ...
    
    @abstractmethod
    def update_task_assignment(self, worker_name: str, pid: int, task_id: str) -> bool:
        """更新任务分配"""
        ...
    
    @abstractmethod
    def clear_task_assignment(self, worker_name: str, pid: int) -> bool:
        """清除任务分配"""
        ...
