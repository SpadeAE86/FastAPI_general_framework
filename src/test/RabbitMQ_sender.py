import pika, time

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
    # 先发送消息
    send_message()

    # 等待1秒后接收消息
    time.sleep(1)
