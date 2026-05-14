from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from config.config import ENV, MY_CONFIG
from infra.logging.logger import logger as log

_engine: Optional[AsyncEngine] = None
_engine_lock = asyncio.Lock()


def resolve_mix_overall_time_mysql_config() -> Dict[str, Any]:
    """``mix_video_overall_time`` 所在库：默认固定用 ``mysql.test``（测试 ai_recommend*），与应用主库分离。"""
    name = (os.getenv("MIX_OVERALL_TIME_MYSQL_ENV") or "").strip()
    mix_cfg = MY_CONFIG.get("mix_compose") or {}
    if not name:
        name = str(mix_cfg.get("overall_time_mysql_env") or "test").strip()
    block = (MY_CONFIG.get("mysql") or {}).get(name)
    if not block:
        log.warning(
            "mix_overall_time: mysql.%s not found, falling back to mysql.%s",
            name,
            ENV,
        )
        block = (MY_CONFIG.get("mysql") or {}).get(ENV) or (MY_CONFIG.get("mysql") or {}).get("local")
    if not block:
        raise RuntimeError("No mysql config for mix_video_overall_time (set mix_compose.overall_time_mysql_env)")
    return block


async def get_mix_overall_time_engine() -> AsyncEngine:
    global _engine
    async with _engine_lock:
        if _engine is None:
            cfg = resolve_mix_overall_time_mysql_config()
            url = (
                f"mysql+aiomysql://{cfg['username']}:{cfg['password']}"
                f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
            )
            _engine = create_async_engine(url, pool_pre_ping=True)
            log.info(
                "mix_video_overall_time DB: %s:%s/%s",
                cfg.get("host"),
                cfg.get("port"),
                cfg.get("database"),
            )
        return _engine


async def dispose_mix_overall_time_engine() -> None:
    global _engine
    async with _engine_lock:
        if _engine is not None:
            await _engine.dispose()
            _engine = None
