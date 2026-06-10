import sys
from unittest.mock import MagicMock

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
