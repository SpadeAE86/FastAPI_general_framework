"""
RabbitMQ Management API 工具类
用于查询 RabbitMQ 队列状态、长度等信息
"""
import time
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, Any, Tuple
from urllib.parse import quote
from config.config import my_config, ENV
from utils.log_utils import logger as log


class RabbitMQManagementClient:
    """RabbitMQ Management API 客户端"""

    def __init__(self):
        rabbitmq_config = my_config.get("rabbitmq", {}).get(ENV, {})

        self.host = rabbitmq_config.get("host", "localhost")
        self.username = rabbitmq_config.get("username", "guest")
        self.password = rabbitmq_config.get("password", "guest")
        self.vhost = rabbitmq_config.get("vhost", "/")

        # 新增：是否使用 SSL
        self.use_ssl = rabbitmq_config.get("use_ssl", False)

        # Management API 端口
        self.management_port = rabbitmq_config.get(
            "management_port",
            15671 if self.use_ssl else 15672
        )

        # 根据 use_ssl 选择 scheme
        scheme = "https" if self.use_ssl else "http"

        # 构建基础 URL（关键点）
        self.base_url = f"{scheme}://{self.host}:{self.management_port}/api"

        # HTTP Basic Auth
        self.auth = HTTPBasicAuth(self.username, self.password)

        # 队列信息本地缓存：key=queue_name, value=(info_dict, expire_timestamp)
        # 避免每次调度循环都打 Management API，降低轮询压力
        self._queue_cache: Dict[str, Tuple[Optional[Dict], float]] = {}
        self._cache_ttl: float = my_config.get("dispatcher", {}).get("queue_cache_ttl", 10.0)

        log.info(
            f"RabbitMQ Management API initialized: "
            f"base_url={self.base_url}, vhost={self.vhost}, ssl={self.use_ssl}, "
            f"queue_cache_ttl={self._cache_ttl}s"
        )
    
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
        获取队列详细信息（带本地 TTL 缓存）

        dispatcher 每 1 秒一轮、每轮对每种 task_type 都轮询一次，
        会产生大量重复 HTTP 请求。这里加了本地 TTL 缓存：
            - 缓存有效期内（默认 10 秒）：直接返回上次结果，不打网络
            - 缓存过期后：发一次真实 HTTP 请求，刷新缓存

        TTL 可通过 config.yml dispatcher.queue_cache_ttl 配置（单位：秒）。
        """
        now = time.monotonic()

        # 命中缓存且未过期 → 直接返回，不打 Management API
        cached_info, expire_at = self._queue_cache.get(queue_name, (None, 0.0))
        if now < expire_at:
            log.debug(f"[队列缓存命中] {queue_name}, 剩余 {expire_at - now:.1f}s")
            return cached_info

        # 缓存已过期，打一次真实请求
        log.info(f"get info for {queue_name}")
        try:
            encoded_vhost = self._encode_vhost(self.vhost)
            url = f"{self.base_url}/queues/{encoded_vhost}/{queue_name}"
            log.debug(f"url={url}")
            response = requests.get(
                url,
                auth=self.auth,
                timeout=5,
                verify=False
            )

            if response.status_code == 200:
                queue_info = response.json()
                log.debug(f"成功获取队列 {queue_name} 信息: {queue_info}")
            elif response.status_code == 404:
                log.warning(f"队列 {queue_name} 不存在")
                queue_info = None
            else:
                log.error(f"获取队列信息失败，状态码: {response.status_code}, 响应: {response.text}")
                queue_info = None

        except requests.exceptions.RequestException as e:
            log.error(f"调用 RabbitMQ Management API 时发生网络错误: {e}")
            queue_info = None  # 网络失败时，返回 None 但不缓存（下次立刻重试）
            return queue_info
        except Exception as e:
            log.error(f"获取队列信息时发生未知错误: {e}", exc_info=True)
            return None

        # 写入缓存（即使结果是 None，也缓存，避免每秒都去打一个不存在的队列）
        self._queue_cache[queue_name] = (queue_info, now + self._cache_ttl)
        return queue_info
    
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

def encode_vhost(vhost: str) -> str:
    if vhost == "/":
        return "%2F"
    return quote(vhost, safe="")

rabbit_mq_config = my_config.get("rabbitmq", {}).get(ENV, {})

def connect_management_api():
    # ===== 你的 prod 配置 =====
    host = "1.94.126.253"

    management_port = 15672   # SSL management 默认端口
    username = "freeu-rabbit"
    password = "RootDev123"
    vhost = "/"
    queue_name = "local_video_queue"

    use_ssl = True

    scheme = "https" if use_ssl else "http"

    encoded_vhost = encode_vhost(vhost)

    url = f"{scheme}://{host}:{management_port}/api/queues/{encoded_vhost}/{queue_name}"

    print("请求 URL:", url)

    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(username, password),
            timeout=5,

            # ⚠️ 内网自签证书通常需要这个
            verify=False
        )

        print("status:", response.status_code)

        if response.status_code == 200:
            data = response.json()

            print("=== 成功 ===")
            print("messages:", data.get("messages"))
            print("messages_ready:", data.get("messages_ready"))
            print("messages_unacknowledged:", data.get("messages_unacknowledged"))
            print("consumers:", data.get("consumers"))

        else:
            print("失败:", response.text)

    except Exception as e:
        print("异常:", e)


if __name__ == "__main__":
    connect_management_api()
# if __name__ == "__main__":
#     # 替换为你的 RabbitMQ 管理端信息
#     host = "123.60.104.114"
#     port = 15672
#     username = "guest"
#     password = "guest"
#     vhost = "/"  # 默认 vhost
#
#     rabbit_api = RabbitMQManagementClient()
#
#     # 测试几个队列
#     test_queues = ["local_video_queue", "nonexistent_queue"]
#
#     for q in test_queues:
#         print(f"\n==== 测试队列: {q} ====")
#         info = rabbit_api.get_queue_info(q)
#         if info:
#             print(f"队列信息: messages={info.get('messages')}, consumers={info.get('consumers')}")
#         else:
#             print("未获取到队列信息")