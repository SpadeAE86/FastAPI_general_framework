"""
RabbitMQ Management API 工具类
用于查询 RabbitMQ 队列状态、长度等信息
"""
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, Any
from urllib.parse import quote
from config.config import my_config, ENV
from utils.log_utils import logger as log


class RabbitMQManagementClient:
    """RabbitMQ Management API 客户端"""
    
    def __init__(self):
        """
        初始化 RabbitMQ Management API 客户端
        
        从配置文件中读取连接信息：
        - host: RabbitMQ 服务器地址
        - username: 用户名
        - password: 密码
        - vhost: 虚拟主机（默认为 "/"）
        """
        rabbitmq_config = my_config.get("rabbitmq", {}).get(ENV, {})
        self.host = rabbitmq_config.get("host", "localhost")
        self.username = rabbitmq_config.get("username", "guest")
        self.password = rabbitmq_config.get("password", "guest")
        self.vhost = rabbitmq_config.get("vhost", "/")
        self.management_port = 15672  # Management API 默认端口
        
        # 构建基础 URL
        self.base_url = f"http://{self.host}:{self.management_port}/api"
        
        # HTTP Basic Auth
        self.auth = HTTPBasicAuth(self.username, self.password)
    
    def _encode_vhost(self, vhost: str) -> str:
        """
        编码 vhost 路径
        
        Args:
            vhost: 虚拟主机路径
            
        Returns:
            编码后的 vhost 路径
        """
        if vhost == "/":
            return "%2F"
        return quote(vhost, safe="")
    
    def get_queue_info(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """
        获取队列详细信息
        
        Args:
            queue_name: 队列名称
            
        Returns:
            队列信息字典，包含以下字段：
            - messages_ready: 准备好传递的消息数
            - messages_unacknowledged: 未确认的消息数
            - messages: 总消息数
            - consumers: 消费者数量
            - 等其他队列信息
            如果获取失败返回 None
        """
        try:
            encoded_vhost = self._encode_vhost(self.vhost)
            url = f"{self.base_url}/queues/{encoded_vhost}/{queue_name}"
            
            response = requests.get(
                url,
                auth=self.auth,
                timeout=5
            )
            
            if response.status_code == 200:
                queue_info = response.json()
                log.debug(f"成功获取队列 {queue_name} 信息: {queue_info}")
                return queue_info
            elif response.status_code == 404:
                log.warning(f"队列 {queue_name} 不存在")
                return None
            else:
                log.error(f"获取队列信息失败，状态码: {response.status_code}, 响应: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            log.error(f"调用 RabbitMQ Management API 时发生网络错误: {e}")
            return None
        except Exception as e:
            log.error(f"获取队列信息时发生未知错误: {e}", exc_info=True)
            return None
    
    def get_queue_length(self, queue_name: str) -> int:
        """
        获取队列长度（消息总数）
        
        Args:
            queue_name: 队列名称
            
        Returns:
            队列中的消息总数（messages_ready + messages_unacknowledged）
            如果获取失败返回 0
        """
        queue_info = self.get_queue_info(queue_name)
        
        if not queue_info:
            return 0
        
        messages_ready = queue_info.get("messages_ready", 0)
        messages_unacknowledged = queue_info.get("messages_unacknowledged", 0)
        total_messages = messages_ready + messages_unacknowledged
        
        log.debug(
            f"队列 {queue_name} 长度: ready={messages_ready}, "
            f"unacked={messages_unacknowledged}, total={total_messages}"
        )
        
        return total_messages
    
    def check_queue_exists(self, queue_name: str) -> bool:
        """
        检查队列是否存在
        
        Args:
            queue_name: 队列名称
            
        Returns:
            队列是否存在
        """
        queue_info = self.get_queue_info(queue_name)
        return queue_info is not None

