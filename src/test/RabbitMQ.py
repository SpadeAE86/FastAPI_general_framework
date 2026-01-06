import pika

def simple_connection_test():
    """最简单的连接测试"""
    credentials = pika.PlainCredentials('root', 'RootDev123')
    parameters = pika.ConnectionParameters(
        host='123.60.104.114',  # 你的ECS公网IP
        port=5672,
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2
    )

    try:
        connection = pika.BlockingConnection(parameters)
        print("✓ 连接成功！")
        # print(f"服务端属性: {connection.server_properties}")
        connection.close()
        return True
    except pika.exceptions.AMQPConnectionError as e:
        print(f"✗ 连接失败: {e}")
        return False


def send_message():
    """发送消息到队列"""
    credentials = pika.PlainCredentials('root', 'RootDev123')
    parameters = pika.ConnectionParameters(
        host='123.60.104.114',
        port=5672,
        credentials=credentials
    )

    try:
        # 建立连接
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        # 声明队列（如果不存在则创建）
        channel.queue_declare(queue='hello', durable=True)  # durable=True 使队列持久化

        # 发送消息
        message = "Hello RabbitMQ!"
        channel.basic_publish(
            exchange='',  # 使用默认的direct exchange
            routing_key='hello',  # 队列名
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # 使消息持久化
            )
        )
        print(f"✓ 消息发送成功: {message}")

        # 关闭连接
        connection.close()
    except Exception as e:
        print(f"✗ 发送消息失败: {e}")


if __name__ == "__main__":
    simple_connection_test()