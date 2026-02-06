import json
import ssl
from typing import Optional, Dict, Any

import pika

from config.config import my_config, ENV


class MQProducer:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool,
    ):
        credentials = pika.PlainCredentials(username, password)
        # ssl_options = pika.SSLOptions(
        #     ssl_context,
        #     server_hostname=host
        # )
        ssl_options = None
        if use_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE  # ⚠️ 和你 Celery 现在一致

            ssl_options = pika.SSLOptions(
                context=ssl_context,
                server_hostname=host,  # pika 要这个
            )
        self.params = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=credentials,
            ssl_options=ssl_options,  # ⭐ 关键就在这
            heartbeat=60,  # ⭐ 必须
            blocked_connection_timeout=300,  # ⭐ 防止 publish 卡死
            socket_timeout=10,  # ⭐ 防止 send 卡住
            connection_attempts=3,
            retry_delay=5
        )

        self.connection: Optional[pika.BlockingConnection] = None


    def _ensure_connection(self):
        if not self.connection or self.connection.is_closed:
            self.connection = pika.BlockingConnection(self.params)
            self.channel = self.connection.channel()

    def send(self, queue, message, headers: Optional[Dict[str, Any]] = None):
        """
        发送消息到指定队列

        Args:
            queue: 队列名称
            message: 消息体
            headers: 自定义headers
        """
        processed_headers = {}
        if headers and type(headers) is dict:
            processed_headers.update(headers)
            # 确保所有值为字符串
            for key, value in processed_headers.items():
                if value is None:
                    processed_headers[key] = ""
                elif isinstance(value, str):
                    processed_headers[key] = value  # 字符串直接使用
                elif isinstance(value, (int, float)):
                    processed_headers[key] = str(value)  # 数字转字符串
                elif isinstance(value, bool):
                    processed_headers[key] = "true" if value else "false"  # 布尔值转字符串
                elif isinstance(value, (dict, list)):
                    processed_headers[key] = json.dumps(value)  # 复杂类型转JSON
                else:
                    processed_headers[key] = str(value)  # 其他类型转字符串

        self._ensure_connection()
        self.channel.queue_declare(queue=queue, durable=True)
        self.channel.basic_publish(
            exchange="",
            routing_key=queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2,
                headers=processed_headers
            )
        )

def rabbitmq_producer_maker() -> MQProducer:
    rabbit_mq_config = my_config.get("rabbit_mq", {}).get(ENV, {})
    host = rabbit_mq_config.get("host", "123.60.104.114")
    password = rabbit_mq_config.get("password", "RootDev123")
    port = rabbit_mq_config.get("port", 5672)
    username = rabbit_mq_config.get("username", "root")
    use_ssl = rabbit_mq_config.get("use_ssl", False)
    rabbit_mq_producer = MQProducer(host, port, username, password, use_ssl=use_ssl)
    return rabbit_mq_producer

mq_producer = MQProducer('123.60.104.114', 5672, 'root', 'RootDev123', use_ssl=False)

