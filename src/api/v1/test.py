"""
视频处理API路由
"""
import datetime
import json
from datetime import datetime

from fastapi import APIRouter

from config.config import my_config
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.mixed_video_response import MixedVideoResponse
from service.mixed_video_service import mixed_video_service
from utils.general_utils import random_with_system_time
from utils.log_utils import logger as log

test_router = APIRouter(prefix="/api/v1/test", tags=["test"])


@test_router.post("/mix")
async def test_video_mix(mixed_config: MixedVideoRequest) -> MixedVideoResponse:
    """
    接收视频剪辑请求，创建任务并写入用户队列

    Args:
        mixed_config: 视频混剪配置

    Returns:
        包含task_id和状态的响应
    """
    project_id = "mix_" + str(random_with_system_time()) if not mixed_config.mix_id else "mix_" + str(
        mixed_config.mix_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")

    current_time = datetime.now()
    log.info(f"{len(mixed_config.obs_video_path_list)}个视频的混剪请求")
    log.info(f"于{current_time}收到请求体")
    log.info(f"{json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
    log.info(f"env: {my_config['env']}")

    resp: MixedVideoResponse = await mixed_video_service(mixed_config)
    return resp