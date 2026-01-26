import json
from typing import Optional

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
            credentials=credentials
        )
        self.connection: Optional[pika.BlockingConnection] = None


    def _ensure_connection(self):
        if not self.connection or self.connection.is_closed:
            self.connection = pika.BlockingConnection(self.params)
            self.channel = self.connection.channel()

    def send(self, queue, message):
        self._ensure_connection()
        self.channel.queue_declare(queue=queue, durable=True)
        self.channel.basic_publish(
            exchange="",
            routing_key=queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )

mq_producer = MQProducer('123.60.104.114', 5672, 'root', 'RootDev123')