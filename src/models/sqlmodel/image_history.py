from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text, DateTime, func, BigInteger
from sqlalchemy.dialects.mysql import JSON as MySQLJSON, VARCHAR


class ImageHistoryCard(SQLModel, table=True):
    """
    每条生图 / 异步生图记录一行（生视频实验室当前仍走 JSON 文件，不经此表）。

    - ``numeric_id``: 自增主键；API 对外 ``id`` 字段为其十进制字符串（短、好记）。
    - ``legacy_id``: 原字符串主键（UUID / 占位 / 与豆包 task_id 同值的异步键），唯一；查询时可继续用旧 id 或 ``taskId`` 命中行。
    """

    __tablename__ = "image_history_cards"

    numeric_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    legacy_id: str = Field(sa_column=Column(VARCHAR(64), nullable=False, unique=True))

    prompt: str = Field(sa_column=Column(Text, nullable=False))
    model: str = Field(sa_column=Column(Text, nullable=False))

    size: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    resolution: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    ratio: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    duration: Optional[int] = Field(default=None, nullable=True)

    doubao_url: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    obs_url: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    time: str = Field(sa_column=Column(Text, nullable=False))
    type: str = Field(sa_column=Column(Text, nullable=False))

    referenceMedia: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(MySQLJSON, nullable=True),
    )
    error: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    taskId: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    status: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    request_id: Optional[str] = Field(default=None, sa_column=Column(VARCHAR(36), nullable=True))

    current_run_started_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    )
