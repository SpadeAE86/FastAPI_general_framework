"""
视频处理API路由
"""
import datetime
import json
from datetime import datetime

from fastapi import APIRouter, Header

from config.config import my_config, ENV
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.request.sprite_image_request import SpriteImageRequest
from models.pydantic_models.request.transcode_video_request import TranscodeVideoRequest
from models.pydantic_models.response.mixed_video_response import MixedVideoResponse
from models.pydantic_models.response.sprite_image_response import SpriteImageResponse
from models.pydantic_models.response.transcode_video_response import TranscodeVideoResponse
from service.mixed_video_service import mixed_video_service
from service.sprite_service import sprite_service
from service.transcode_video_service import transcode_video_service
from utils.general_utils import random_with_system_time
from utils.log_utils import logger as log
from utils.post_utils import post

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

    project_id = "mix_" + str(random_with_system_time()) if not mixed_config.biz_id else "mix_" + str(
        mixed_config.biz_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")

    current_time = datetime.now()
    log.info(f"{len(mixed_config.obs_video_path_list)}个视频的混剪请求")
    log.info(f"于{current_time}收到请求体")
    log.info(f"{json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
    log.info(f"env: {my_config['env']}")

    resp: MixedVideoResponse = await mixed_video_service(mixed_config)
    return resp


@test_router.post("/sprite", response_model=SpriteImageResponse)
async def test_sprite(sprite_request: SpriteImageRequest, trace_id = Header(None)) -> SpriteImageResponse:
    """
    雪碧图测试接口（不走 Celery）

    - 直接调用 sprite_service
    - 用于本地 / 联调 / 验证参数
    """
    log.info(f"received Trace-Id: {trace_id}")
    project_id = (
        "sprite_" + str(random_with_system_time())
        if not sprite_request.biz_id
        else "sprite_" + str(sprite_request.biz_id)
    )

    log.info(f"project_id: {project_id}")

    current_time = datetime.now()
    log.info(f"雪碧图请求于 {current_time} 收到")
    log.info(
        json.dumps(
            sprite_request.model_dump(exclude_none=True),
            indent=2,
            ensure_ascii=False
        )
    )
    log.info(f"env: {my_config['env']}")

    # 核心处理
    resp: SpriteImageResponse = await sprite_service(sprite_request)

    log.info(
        f"生成雪碧图成功: project_id={project_id}, "
        f"sprite_count={len(resp.sprite_image_url_list)}"
    )

    return resp

@test_router.post("/transcode", response_model=TranscodeVideoResponse)
async def test_video_transcode(
    transcode_request: TranscodeVideoRequest
) -> TranscodeVideoResponse:
    """
    转码测试接口（不走 Celery）

    - 直接调用 transcode_video_service
    - 用于本地 / 联调 / 参数验证
    """
    project_id = (
        "transcode_" + str(random_with_system_time())
        if not transcode_request.biz_id
        else "transcode_" + str(transcode_request.biz_id)
    )

    log.info(f"project_id: {project_id}")

    current_time = datetime.now()
    log.info(f"转码请求于 {current_time} 收到")
    log.info(
        json.dumps(
            transcode_request.model_dump(exclude_none=True),
            indent=2,
            ensure_ascii=False
        )
    )
    log.info(f"env: {my_config['env']}")

    video_path = transcode_request.obs_video_path
    if not video_path or not isinstance(video_path, str):
        raise ValueError("请求缺少 video_path")

    # 核心处理
    resp: TranscodeVideoResponse = await transcode_video_service(transcode_request)

    log.info(
        f"转码完成: project_id={project_id}, "
        f"file_id={getattr(resp, 'file_id', None)}"
    )

    return resp