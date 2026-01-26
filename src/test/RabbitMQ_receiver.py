import pika

def receive_message():
    """接收队列中的消息"""
    credentials = pika.PlainCredentials('root', 'RootDev123')
    parameters = pika.ConnectionParameters(
        host='123.60.104.114',
        port=5672,
        credentials=credentials
    )

    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        # 声明队列（确保队列存在）
        channel.queue_declare(queue='test_transcode_result_queue', durable=True)

        print("等待接收消息... 按 Ctrl+C 退出")

        def callback(ch, method, properties, body):
            """收到消息时的回调函数"""
            print(f"✓ 收到消息: {body.decode()}")
            # 手动确认消息已处理
            ch.basic_ack(delivery_tag=method.delivery_tag)

        # 设置公平分发，防止一个消费者占用所有消息
        channel.basic_qos(prefetch_count=1)

        # 开始消费消息
        channel.basic_consume(
            queue='test_transcode_result_queue',
            on_message_callback=callback,
            auto_ack=False  # 关闭自动确认，改为手动确认
        )

        channel.start_consuming()

    except KeyboardInterrupt:
        print("\n程序退出")
        connection.close()
    except Exception as e:
        print(f"✗ 接收消息失败: {e}")

if __name__ == "__main__":
    # 先发送消息


    # 接收消息（这个会一直运行等待新消息）
    receive_message()
