import sys
import os
import json
import uuid

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), "src"))

from celery_mq.task_manager import task_manager
from celery_mq.task_repository import TaskRepository
from utils.redis_client import RedisClientFactory

def verify_task_result():
    print("Starting Task Manager Result Verification...")
    
    # Generate dummy user and task data
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    task_data = {"type": "test", "payload": "dummy_data"}
    
    # 1. Create Task
    print(f"Creating task for user {user_id}...")
    try:
        task_id = task_manager.create_task(user_id, task_data)
        print(f"Task created with ID: {task_id}")
    except Exception as e:
        print(f"Failed to create task: {e}")
        return

    # 2. Verify initial state
    task_info = task_manager.get_task_status(task_id)
    print(f"Initial Task Info: {json.dumps(task_info, indent=2, ensure_ascii=False)}")
    
    if task_info.get("result") == "null" or task_info.get("result") is None:
        print("✅ Initial result is correct (null/None)")
    else:
        print(f"❌ Initial result is incorrect: {task_info.get('result')}")
        
    # 3. Update task with result
    result_payload = {
        "status": "success", 
        "data": {"video_url": "http://example.com/vid.mp4", "size": 1024}
    }
    print(f"Updating task with result: {result_payload}")
    task_manager.update_task_status(task_id, "completed", result=result_payload)
    
    # 4. Verify updated state
    updated_task_info = task_manager.get_task_status(task_id)
    print(f"Updated Task Info: {json.dumps(updated_task_info, indent=2, ensure_ascii=False)}")
    
    retrieved_result = updated_task_info.get("result")
    
    if retrieved_result == result_payload:
        print("✅ Result verification SUCCESS: Retrieved result matches stored result.")
    else:
        print(f"❌ Result verification FAILED!")
        print(f"Expected: {result_payload}")
        print(f"Got: {retrieved_result}")

    # Cleanup (Optional, but good practice)
    # task_manager.delete_task(task_id)
    # print("Test task cleaned up.")

if __name__ == "__main__":
    verify_task_result()
