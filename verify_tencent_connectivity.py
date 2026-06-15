import os
import sys
import asyncio
import time
from pathlib import Path

# 强制设置平台为 tencent，环境为 test
os.environ["PLATFORM"] = "tencent"
os.environ["ENV"] = "test"

# 将项目根目录的 src 目录加入到 sys.path，保证可以正常导入模块
project_root = Path(__file__).resolve().parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 导入配置和数据库/客户端模块
try:
    from config.config import my_config, ENV
    from utils.redis_client import get_redis_client
    from database.mysql.mysql_manager import db_manager
    from sqlalchemy import text
    from utils.mq.rabbit_mq_producer import rabbitmq_producer_maker
    import redis
    import pika
except ImportError as e:
    print(f"[-] 导入模块失败: {e}")
    sys.exit(1)

async def test_mysql_connection():
    print("-> 正在测试 MySQL 连通性...")
    mysql_cfg = my_config.get("mysql", {}).get(ENV, {})
    print(f"   目标: {mysql_cfg.get('host')}:{mysql_cfg.get('port')} (库名: {mysql_cfg.get('database')}, 用户: {mysql_cfg.get('username')})")
    
    start_time = time.time()
    try:
        # 使用 asyncio.wait_for 限制连接超时时间，防止因内网 IP 无法连接而导致无限挂起
        async def do_connect():
            async with db_manager.main_engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.fetchone()

        row = await asyncio.wait_for(do_connect(), timeout=5.0)
        duration = time.time() - start_time
        if row and row[0] == 1:
            print(f"   [OK] MySQL 连接成功! (耗时: {duration:.2f}s)")
            return True
        else:
            print(f"   [FAILED] MySQL 连接失败: 返回数据不符合预期 {row}")
            return False
    except asyncio.TimeoutError:
        print("   [FAILED] MySQL 连接超时 (5秒内未响应，可能是网络不通或 IP 无法访问)")
        return False
    except Exception as e:
        print(f"   [FAILED] MySQL 连接异常: {e}")
        return False

def test_redis_connection():
    print("-> 正在测试 Redis 连通性...")
    redis_cfg = my_config.get("redis", {}).get(ENV, {})
    print(f"   目标: {redis_cfg.get('host')}:{redis_cfg.get('port')} (DB: {redis_cfg.get('database')})")
    
    start_time = time.time()
    try:
        # 直接实例化一个带超时限制的 redis 客户端进行 ping，避免使用全局客户端导致挂起
        client = redis.Redis(
            host=redis_cfg.get("host", "127.0.0.1"),
            port=redis_cfg.get("port", 6379),
            db=redis_cfg.get("database", 0),
            password=redis_cfg.get("password"),
            socket_connect_timeout=3,
            socket_timeout=3,
            decode_responses=True
        )
        if client.ping():
            duration = time.time() - start_time
            print(f"   [OK] Redis 连接成功! (耗时: {duration:.2f}s)")
            return True
        else:
            print("   [FAILED] Redis 连接失败: ping 未返回 True")
            return False
    except redis.exceptions.TimeoutError:
        print("   [FAILED] Redis 连接超时 (3秒内未响应，可能是网络不通或 IP 无法访问)")
        return False
    except Exception as e:
        print(f"   [FAILED] Redis 连接异常: {e}")
        return False

def test_rabbitmq_connection():
    print("-> 正在测试 RabbitMQ 连通性...")
    rabbitmq_cfg = my_config.get("rabbitmq", {}).get(ENV, {})
    print(f"   目标: {rabbitmq_cfg.get('host')}:{rabbitmq_cfg.get('port')} (用户: {rabbitmq_cfg.get('username')})")
    
    start_time = time.time()
    try:
        # 设置超时参数
        credentials = pika.PlainCredentials(rabbitmq_cfg.get("username"), rabbitmq_cfg.get("password"))
        params = pika.ConnectionParameters(
            host=rabbitmq_cfg.get("host"),
            port=rabbitmq_cfg.get("port"),
            credentials=credentials,
            socket_timeout=3,
            connection_attempts=1,
            retry_delay=1
        )
        connection = pika.BlockingConnection(params)
        if connection.is_open:
            duration = time.time() - start_time
            print(f"   [OK] RabbitMQ 连接成功! (耗时: {duration:.2f}s)")
            connection.close()
            return True
        else:
            print("   [FAILED] RabbitMQ 连接失败: 连接未开启")
            return False
    except pika.exceptions.AMQPConnectionError as e:
        print(f"   [FAILED] RabbitMQ 连接失败 (AMQP 错误): {e}")
        return False
    except Exception as e:
        print(f"   [FAILED] RabbitMQ 连接异常: {e}")
        return False

async def main():
    print("=" * 60)
    print("          腾讯云测试环境连通性检查工具")
    print("=" * 60)
    print(f"当前平台配置: {my_config.get('platform')}")
    print(f"当前运行环境: {ENV}")
    print("-" * 60)
    
    # 依次测一下 redis, mysql, rabbitmq 连通性
    redis_ok = test_redis_connection()
    print()
    
    mysql_ok = await test_mysql_connection()
    print()
    
    rabbitmq_ok = test_rabbitmq_connection()
    print()
    
    print("=" * 60)
    print("          检查结果汇总")
    print("=" * 60)
    print(f" Redis    连通性: {'[OK] 成功' if redis_ok else '[FAILED] 失败'}")
    print(f" MySQL    连通性: {'[OK] 成功' if mysql_ok else '[FAILED] 失败'}")
    print(f" RabbitMQ 连通性: {'[OK] 成功' if rabbitmq_ok else '[FAILED] 失败'}")
    print("=" * 60)
    
    if not (redis_ok and mysql_ok and rabbitmq_ok):
        print("\n提示: 如果在腾讯云 VPC 外部的开发机运行此脚本，由于腾讯云的测试数据库和队列 IP（172.16.5.x）是内网私有 IP，连接失败属正常现象，需要在对应的腾讯云 VPC 网络环境内运行方可连通。")

if __name__ == "__main__":
    asyncio.run(main())
