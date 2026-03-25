import sys
import os
import uuid
import time
from typing import Dict, Any

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from celery_mq.task_manager import task_manager
from core.dispatcher.service import DispatcherService
import config.config as config
# Force local environment for verification testing
config.ENV = "local"
from config.config import ENV
from utils.redis_client import RedisClientFactory
from celery_mq.task_manager import task_manager
from core.dispatcher.service import DispatcherService

# Force-reconnect task_manager to local redis
local_client = RedisClientFactory.get_client()
task_manager.redis_client = local_client
task_manager._repository.redis = local_client
task_manager._hash_service.redis = local_client
task_manager._queue_service.redis = local_client

def simulate_hol_blocking():
    print("=== Simulating Task Queue Isolation ===")
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    redis = RedisClientFactory.get_client()
    
    # 1. Clean up potential old keys
    # Keys follow: f"{ENV}:pending:tasks:{user_id}:{task_type}"
    # and f"{ENV}:user:active_types:{user_id}"
    
    # 2. Add 5 'mix' tasks (we'll simulate flow control for 'mix')
    print(f"Adding 5 'mix' tasks for {user_id}...")
    for i in range(5):
        task_data = {"user_id": user_id, "task_type": "mix", "data": f"mix_{i}"}
        task_manager.create_task(user_id, task_data)
        
    # 3. Add 1 'sprite' task (non-limited)
    print(f"Adding 1 'sprite' task for {user_id}...")
    sprite_task_data = {"user_id": user_id, "task_type": "sprite", "data": "sprite_1"}
    sprite_task_id = task_manager.create_task(user_id, sprite_task_data)
    
    # 4. Initialize Dispatcher and simulate flow control: mix=False, sprite=True
    dispatcher = DispatcherService()
    # Mock flow control results
    flow_control_mock = {"mix": False, "sprite": True}
    
    print("\n--- Dispatcher Selection ---")
    print(f"Flow Control Status: {flow_control_mock}")
    
    # Run weighted_round_robin
    dispatched_task_ids = dispatcher.weighted_round_robin(flow_control_mock)
    
    print(f"Dispatched Task IDs: {dispatched_task_ids}")
    
    # 5. Verification
    if sprite_task_id in dispatched_task_ids:
        print("\nSUCCESS: 'sprite' task was dispatched despite 'mix' tasks being at the head of the logical timeline.")
    else:
        print("\nFAILURE: 'sprite' task was blocked or not found.")
        
    for tid in dispatched_task_ids:
        t_info = task_manager.get_task_status(tid)
        if t_info.get('task_type') == 'mix':
            print(f"ERROR: 'mix' task {tid} was dispatched while under flow control!")
            
    # Check Redis keys for multi-queue structure
    mix_key = f"{ENV}:pending:tasks:{user_id}:mix"
    sprite_key = f"{ENV}:pending:tasks:{user_id}:sprite"
    active_types_key = f"{ENV}:user:active_types:{user_id}"
    
    print(f"\nRedis Key Inspection:")
    print(f"Mix Queue Length: {redis.llen(mix_key)}")
    print(f"Sprite Queue Length: {redis.llen(sprite_key)}")
    print(f"Active Types: {redis.smembers(active_types_key)}")

if __name__ == "__main__":
    simulate_hol_blocking()
