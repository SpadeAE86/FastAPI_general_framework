import sys
from unittest.mock import MagicMock

# Mock redis modules to prevent connecting to actual Redis
mock_redis = MagicMock()
sys.modules['redis'] = mock_redis
sys.modules['redis.exceptions'] = mock_redis

# Create mock client factory
mock_client = MagicMock()
mock_client.ping.return_value = True
mock_client.get.return_value = None

class MockRedisClientFactory:
    @classmethod
    def get_client(cls):
        return mock_client

sys.modules['utils.redis_client'] = MagicMock(RedisClientFactory=MockRedisClientFactory)

# Mock health_monitor module to prevent initialization errors
sys.modules['core.health_monitor'] = MagicMock()
sys.modules['core.health_monitor.service'] = MagicMock()
sys.modules['core.health_monitor.heartbeat_checker'] = MagicMock()
sys.modules['core.health_monitor.monitor'] = MagicMock()

# Mock the celery tasks module to break the circular import during setup
sys.modules['celery_mq.task.normalize_video_tasks'] = MagicMock()

import json
import asyncio
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from service.mixed_video_service import mixed_video_service

async def main():
    body_path = os.path.abspath('src/utils/body.json')
    with open(body_path, 'r', encoding='utf-8') as f:
        body_data = json.load(f)
    
    req = MixedVideoRequest(**body_data)
    
    print("Running mixed_video_service...")
    try:
        res = await mixed_video_service(req)
        print("Finished mixed_video_service.")
        print(f"Result: {res}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
