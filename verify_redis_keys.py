import sys
import os

# Add src to sys.path
current_dir = os.getcwd()
src_dir = os.path.join(current_dir, 'src')
sys.path.append(src_dir)

try:
    from celery_mq.user_queue_service import UserQueueService
    from celery_mq.task_hash_service import TaskHashService
    from celery_mq.task_repository import TaskRepository
    from config.config import ENV
    
    print(f"Current ENV: {ENV}")
    print("-" * 50)
    
    class MockRedis:
        def __init__(self): pass
        def set(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return None
        def hset(self, *args, **kwargs): pass
        def hgetall(self, *args, **kwargs): return {}
        def expire(self, *args, **kwargs): pass
        def delete(self, *args, **kwargs): pass
        def rpop(self, *args, **kwargs): return None
        def llen(self, *args, **kwargs): return 0
        def srem(self, *args, **kwargs): pass
        def lpush(self, *args, **kwargs): pass
        def lrem(self, *args, **kwargs): pass
        def smembers(self, *args, **kwargs): return []
        def sadd(self, *args, **kwargs): pass

    redis_client = MockRedis()
    
    # 1. Verify UserQueueService
    queue_service = UserQueueService(redis_client)
    print("[UserQueueService]")
    print(f"ACTIVE_USERS_KEY: {queue_service.ACTIVE_USERS_KEY}")
    print(f"VIP_USERS_KEY: {queue_service.VIP_USERS_KEY}")
    print(f"Queue Key (uid='123'): {queue_service._get_queue_key('123')}")
    print("-" * 20)

    # 2. Verify TaskHashService
    hash_service = TaskHashService(redis_client)
    print("[TaskHashService]")
    print(f"Hash Key (hash='abcdef'): {hash_service._get_hash_key('abcdef')}")
    print("-" * 20)

    # 3. Verify TaskRepository
    repo = TaskRepository(redis_client)
    print("[TaskRepository]")
    print(f"Task Key (tid='task_1'): {repo._get_task_key('task_1')}")
    print(f"Task Data Key (tid='task_1'): {repo._get_task_data_key('task_1')}")
    print(f"Subtasks Key (tid='task_1'): {repo._get_subtasks_key('task_1')}")
    print(f"Start Time Key (tid='task_1'): {repo._get_start_time_key('task_1')}")
    print(f"Subtask Key (verify logic): {ENV}:subtask:sub_1") # logic verified by reading code calling delete/get
    
    
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
