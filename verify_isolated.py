import sys
import os
import uuid
from typing import Dict, List, Any
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Mock the entire config and redis before any imports that might use them
import config.config as config
config.ENV = "local"

# 1. Create a fully Mock TaskManager
class MockTaskManager:
    def __init__(self):
        print("MockTaskManager initialized")
        self.user_queues = {} # {user_id: {type: [ids]}}
        self.active_types = {} # {user_id: set(types)}
        self.active_users = []
        
    def get_active_users(self):
        print(f"DEBUG: get_active_users called -> {self.active_users}")
        return self.active_users

    def get_vip_users(self):
        v = getattr(self, "vip_users", [])
        print(f"DEBUG: get_vip_users called -> {v}")
        return v

    def get_user_active_task_types(self, user_id):
        t = list(self.active_types.get(user_id, []))
        print(f"DEBUG: get_user_active_task_types({user_id}) -> {t}")
        return t

    def fetch_tasks_from_user_queue(self, user_id, count, task_type):
        q = self.user_queues.get(user_id, {}).get(task_type, [])
        fetched = q[-count:] if count > 0 else []
        print(f"DEBUG: fetch_tasks_from_user_queue({user_id}, {count}, {task_type}) -> {fetched}")
        # Simulate removal
        if fetched:
            self.user_queues[user_id][task_type] = q[:-len(fetched)]
            if not self.user_queues[user_id][task_type]:
                self.active_types[user_id].remove(task_type)
        return fetched

# 2. Inject Mock into the global namespace
mock_tm = MockTaskManager()
import celery_mq.task_manager
celery_mq.task_manager.task_manager = mock_tm

# Also inject into the core.dispatcher.service module specifically
import core.dispatcher.service
core.dispatcher.service.task_manager = mock_tm

# 3. Now import Dispatcher
from core.dispatcher.service import DispatcherService

def verify_hol_logic():
    print("=== Verifying HoL Fix Logic (Isolated) ===")
    user_id = "test_user_hol"
    
    # Setup: 5 mix tasks, 1 sprite task
    mock_tm.user_queues[user_id] = {
        "mix": ["m1", "m2", "m3", "m4", "m5"],
        "sprite": ["s1"]
    }
    mock_tm.active_types[user_id] = {"mix", "sprite"}
    mock_tm.active_users = [user_id]
    
    # Case: mix=False (blocked), sprite=True (eligible)
    flow_control = {"mix": False, "sprite": True}
    
    dispatcher = DispatcherService()
    dispatcher.normal_task_count = 1
    
    print(f"Initial State: {mock_tm.user_queues[user_id]}")
    print(f"Flow Control: {flow_control}")
    
    # Run scheduling
    dispatched = dispatcher.weighted_round_robin(flow_control)
    
    print(f"Dispatched IDs: {dispatched}")
    
    # Verification
    if "s1" in dispatched:
        print("\nSUCCESS: 'sprite' task (s1) was dispatched!")
    else:
        print("\nFAILURE: 'sprite' task was not dispatched.")
        
    if any(m in dispatched for m in ["m1", "m2", "m3", "m4", "m5"]):
        print("FAILURE: 'mix' tasks were dispatched despite flow control!")
    else:
        print("SUCCESS: 'mix' tasks were correctly skipped.")

if __name__ == "__main__":
    verify_hol_logic()
