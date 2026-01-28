import json
from typing import Optional, Dict, Any

import pika

class MQProducer:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str
    ):
        credentials = pika.PlainCredentials(username, password)
        self.params = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=credentials,
            # heartbeat=60,  # ⭐ 必须
            # blocked_connection_timeout=300,  # ⭐ 防止 publish 卡死
            # socket_timeout=10,  # ⭐ 防止 send 卡住
            # connection_attempts=3,
            # retry_delay=5
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

mq_producer = MQProducer('123.60.104.114', 5672, 'root', 'RootDev123')