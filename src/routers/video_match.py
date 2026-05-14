from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from fastapi import APIRouter, Body, HTTPException

from services.video_match_service import (
    create_job_and_parse,
    get_job_payload,
    get_shot_match_detail,
    list_video_match_jobs,
    run_job_search,
    synthesize_shot_obs_audio,
)
from services.video_mix_compose_service import start_mix_compose_for_job


class VideoMatchCreateJobBody(BaseModel):
    script: str = Field(..., description="口播脚本")
    topic: Optional[str] = None
    title: Optional[str] = None
    car_model: Optional[str] = None
    workspace: Optional[str] = Field(default="v1", description="与视频分析 workspace 对齐")
    mock: bool = Field(default=False, description="true 时返回固定分镜，不写库")


class VideoMatchSearchBody(BaseModel):
    strategy_name: str = Field(..., min_length=1, description="与 video_analysis_search_strategy.name 一致")
    mode: str = Field(default="field_aligned_hybrid", description="match_script_tags_segments mode")
    top_k: int = Field(default=5, ge=1, le=50)


class MixComposeFromJobBody(BaseModel):
    mock: Optional[bool] = Field(
        default=None,
        description="true=仅占位写入 mix 表；false=POST 真实混剪；null=使用 config mix_compose.mock",
    )


video_match_router = APIRouter(prefix="/video-match", tags=["video-match"])


@video_match_router.get("/jobs")
async def list_video_match_jobs_route(
    parse_status: Optional[str] = None,
    workspace: Optional[str] = None,
    limit: int = 50,
):
    return await list_video_match_jobs(parse_status=parse_status, workspace=workspace, limit=limit)


@video_match_router.post("/jobs")
async def create_video_match_job(body: VideoMatchCreateJobBody):
    return await create_job_and_parse(
        script=body.script,
        topic=body.topic,
        title=body.title,
        car_model=body.car_model,
        workspace=body.workspace,
        mock=body.mock,
    )


@video_match_router.get("/jobs/{job_id}")
async def get_video_match_job(job_id: str):
    data = await get_job_payload(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="job not found")
    return data


@video_match_router.get("/jobs/{job_id}/shots/{shot_row_id}/detail")
async def get_video_match_shot_detail(job_id: str, shot_row_id: int):
    data = await get_shot_match_detail(job_id, shot_row_id)
    if data is None:
        raise HTTPException(status_code=404, detail="shot not found")
    return data


@video_match_router.post("/jobs/{job_id}/shots/{shot_row_id}/audio")
async def synthesize_shot_audio_route(job_id: str, shot_row_id: int):
    return await synthesize_shot_obs_audio(job_id, shot_row_id)


@video_match_router.post("/jobs/{job_id}/mix-compose")
async def start_mix_compose_from_match_job(
    job_id: str,
    body: MixComposeFromJobBody = Body(default_factory=MixComposeFromJobBody),
):
    """与 ``POST /video-mix/compose`` 等价，仅路径绑定在匹配 job 上。可选 body: ``{ \"mock\": true|false|null }``。"""
    try:
        return await start_mix_compose_for_job(job_id, mix_mock=body.mock)
    except ValueError as e:
        msg = str(e)
        if msg == "job not found":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e


@video_match_router.post("/jobs/{job_id}/search")
async def search_video_match_job(job_id: str, body: VideoMatchSearchBody):
    return await run_job_search(
        job_id,
        strategy_name=body.strategy_name,
        mode=body.mode,
        top_k=body.top_k,
    )
