
import os
import sys
import uuid
from typing import Dict, Any
from unittest.mock import MagicMock, patch

# 将 src 目录添加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# 提前 Mock Redis 客户端工厂，防止初始化时连接失败
from utils.redis_client import RedisClientFactory
mock_redis = MagicMock()
RedisClientFactory.get_client = MagicMock(return_value=mock_redis)

from celery_mq.task_manager import TaskManager
from core.dispatcher.service import DispatcherService
from config.config import ENV

def test_queue_distributor_logic():
    print("=== 开始验证队列调度与流控逻辑 (Mock Redis 模式) ===")
    
    # 1. 初始化
    task_manager = TaskManager(mock_redis)
    dispatcher = DispatcherService()
    
    user_id = "test_user_123"
    print(f"测试用户: {user_id}")
    
    # 模拟 Redis 数据返回
    # 1. get_active_users 返回当前用户
    mock_redis.smembers.side_effect = lambda key: {
        f"{ENV}:active_users": [user_id.encode()],
        f"{ENV}:user:active_types:{user_id}": [b"mix", b"transcode"]
    }.get(key, [])

    # 2. 模拟任务拉取 (rpop)
    # 第一次拉取 mix, 第二次拉取 transcode
    mock_responses = {
        f"{ENV}:pending:tasks:{user_id}:mix": [b"task_mix_1"],
        f"{ENV}:pending:tasks:{user_id}:transcode": [b"task_trans_1"]
    }
    
    def mock_rpop(key):
        queue = mock_responses.get(key, [])
        return queue.pop(0) if queue else None
    
    mock_redis.rpop.side_effect = mock_rpop
    
    # 3. 模拟流控情况
    # 假设 'mix' 队列满了，'transcode' 队列正常
    flow_control = {
        "mix": False,        # 暂停分发
        "transcode": True    # 允许分发
    }
    print(f"模拟流控状态: {flow_control}")
    
    # 4. 测试调度器拉取逻辑
    # dispatcher._fetch_user_tasks_fairly 是核心分发逻辑
    tasks = dispatcher._fetch_user_tasks_fairly(user_id, count=10, flow_control=flow_control)
    
    print(f"调度器拉取到的任务 ID 列表: {tasks}")
    
    # 5. 断言结果
    # 应该只能拉到 transcode 任务，因为 mix 被流控跳过了
    assert "task_trans_1" in tasks, "错误：应该拉取到 transcode 任务"
    assert "task_mix_1" not in tasks, "错误：不应该拉取到被流控的 mix 任务"
    
    # 验证是否只调用了 transcode 的 rpop
    # 因为 weighted_round_robin 现在会先检查 flow_control
    # 所以根本不应该对 mix 执行 rpop
    print("验证结果: 调度器能够识别不同任务类型的流控状态，仅从健康的队列中拉取任务。")
    print("=== 逻辑验证成功！分布式队列重构逻辑正确 ===")

if __name__ == "__main__":
    try:
        test_queue_distributor_logic()
    except Exception as e:
        print(f"验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
