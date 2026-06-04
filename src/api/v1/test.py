"""
视频、图片和音频的直连测试接口，不走异步队列。
"""
import json
from datetime import datetime

from fastapi import APIRouter, Header, Query

from config.config import my_config
from models.pydantic_models.request.alivoice_request import Alivoice_VO
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.request.sprite_image_request import SpriteImageRequest
from models.pydantic_models.request.transcode_video_request import TranscodeVideoRequest
from models.pydantic_models.request.volcovoice_request import Volcovoice_VO
from models.pydantic_models.response.alivoice_response import AliVoiceResponse
from models.pydantic_models.response.mixed_video_response import MixedVideoResponse
from models.pydantic_models.response.sprite_image_response import SpriteImageResponse
from models.pydantic_models.response.transcode_video_response import TranscodeVideoResponse
from models.pydantic_models.response.volcovoice_response import VolcovoiceResponse
from service.alivoice_service import process_alivoice_task
from service.mixed_video_service import mixed_video_service
from service.sprite_service import sprite_service
from service.transcode_video_service import transcode_video_service
from service.volcovoice_service import process_volcovoice_task
from collect_volcovoice_sample import DEFAULT_VOLCOVOICE_SAMPLE_TEXT, sample_volcovoice_voices
from utils.general_utils import random_with_system_time
from utils.log_utils import logger as log

test_router = APIRouter(prefix="/api/v1/test", tags=["test"])


@test_router.post("/mix")
async def test_video_mix(mixed_config: MixedVideoRequest) -> MixedVideoResponse:
    project_id = "mix_" + str(random_with_system_time()) if not mixed_config.biz_id else "mix_" + str(mixed_config.biz_id)
    log.info(f"project_id: {project_id}")
    log.info(f"{len(mixed_config.obs_video_path_list)}个视频的混剪请求")
    log.info(f"{datetime.now()} 收到请求")
    log.info(json.dumps(mixed_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False))
    log.info(f"env: {my_config['env']}")
    return await mixed_video_service(mixed_config)


@test_router.post("/sprite", response_model=SpriteImageResponse)
async def test_sprite(sprite_request: SpriteImageRequest, trace_id: str = Header(None)) -> SpriteImageResponse:
    log.info(f"received Trace-Id: {trace_id}")
    project_id = "sprite_" + str(random_with_system_time()) if not sprite_request.biz_id else "sprite_" + str(sprite_request.biz_id)
    log.info(f"project_id: {project_id}")
    log.info(f"雪碧图请求于 {datetime.now()} 收到")
    log.info(json.dumps(sprite_request.model_dump(exclude_none=True), indent=2, ensure_ascii=False))
    log.info(f"env: {my_config['env']}")
    return await sprite_service(sprite_request)


@test_router.post("/transcode", response_model=TranscodeVideoResponse)
async def test_video_transcode(transcode_request: TranscodeVideoRequest) -> TranscodeVideoResponse:
    project_id = "transcode_" + str(random_with_system_time()) if not transcode_request.biz_id else "transcode_" + str(transcode_request.biz_id)
    log.info(f"project_id: {project_id}")
    log.info(f"转码请求于 {datetime.now()} 收到")
    log.info(json.dumps(transcode_request.model_dump(exclude_none=True), indent=2, ensure_ascii=False))
    log.info(f"env: {my_config['env']}")

    video_path = transcode_request.obs_video_path
    if not video_path or not isinstance(video_path, str):
        raise ValueError("请求缺少 video_path")

    return await transcode_video_service(transcode_request)


@test_router.post("/alivoice", response_model=AliVoiceResponse)
async def test_alivoice(voice_config: Alivoice_VO, trace_id: str = Header(None)) -> AliVoiceResponse:
    log.info(f"received Trace-Id: {trace_id}")
    log.info(f"alivoice direct request: {json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
    log.info(f"env: {my_config['env']}")
    return await process_alivoice_task(voice_config)


@test_router.post("/volcovoice", response_model=VolcovoiceResponse)
async def test_volcovoice(voice_config: Volcovoice_VO, trace_id: str = Header(None)) -> VolcovoiceResponse:
    log.info(f"received Trace-Id: {trace_id}")
    log.info(f"volcovoice direct request: {json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
    log.info(f"env: {my_config['env']}")
    return await process_volcovoice_task(voice_config)


@test_router.post("/volcovoice_sample", response_model=dict)
async def test_volcovoice_sample(
    k: int = Query(..., ge=1, description="Sample the first k volcovoice characters"),
    resample: bool = Query(False, description="Resample even if the same voice/text pair already exists"),
    txt_content: str = Query(DEFAULT_VOLCOVOICE_SAMPLE_TEXT, description="Text used for voice sampling"),
    concurrency: int = Query(100, ge=1, le=100, description="Concurrent volcovoice sampling workers"),
) -> dict:
    log.info(
        "volcovoice sample request: "
        + json.dumps(
            {
                "k": k,
                "resample": resample,
                "txt_content": txt_content,
                "concurrency": concurrency,
            },
            ensure_ascii=False,
        )
    )
    return await sample_volcovoice_voices(
        k=k,
        resample=resample,
        txt_content=txt_content,
        concurrency=concurrency,
    )
