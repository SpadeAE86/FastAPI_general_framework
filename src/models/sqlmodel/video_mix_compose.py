from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, Text, func
from sqlalchemy.dialects.mysql import JSON as MySQLJSON, VARCHAR


class VideoMixComposeJob(SQLModel, table=True):
    """视频匹配后混剪合成任务：供前端轮询，防 HTTP 超时。biz_id 为三位整数字符串，与混剪 Worker、mix_video_overall_time 一致。"""

    __tablename__ = "video_mix_compose_job"

    id: str = Field(
        sa_column=Column(VARCHAR(36), primary_key=True, nullable=False),
        description="compose_id，UUID",
    )
    biz_id: str = Field(
        sa_column=Column(VARCHAR(36), nullable=False, unique=True, index=True),
    )
    video_match_job_id: Optional[str] = Field(default=None, sa_column=Column(VARCHAR(36), nullable=True, index=True))
    status: str = Field(
        default="pending",
        sa_column=Column(VARCHAR(32), nullable=False),
        description="pending|transcoding|building|submitting|processing|done|failed",
    )
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    result_obs_url: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    request_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(MySQLJSON, nullable=True))

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    )
