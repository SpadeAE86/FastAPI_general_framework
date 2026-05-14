from __future__ import annotations

from sqlmodel import SQLModel
from sqlalchemy import text

from infra.logging.logger import logger as log
from infra.storage.mysql_connector import mysql_connector

# Ensure ORM tables are registered into metadata
import models.sqlmodel  # noqa: F401


async def _ensure_http_request_trace_columns() -> None:
    """create_all 不会给已有表加列；旧库补 http_request_traces 扩展字段。"""
    engine = await mysql_connector.get_engine()
    stmts = [
        "ALTER TABLE http_request_traces ADD COLUMN process_id INT NULL",
        "ALTER TABLE http_request_traces ADD COLUMN upstream_task_id VARCHAR(128) NULL",
        "ALTER TABLE http_request_traces ADD COLUMN business_id VARCHAR(64) NULL",
        "ALTER TABLE http_request_traces ADD COLUMN business_success TINYINT(1) NULL",
    ]
    async with engine.begin() as conn:
        for sql in stmts:
            try:
                await conn.execute(text(sql))
                log.info("Applied HTTP trace column migration: %s", sql[:80])
            except Exception as e:
                msg = str(e).lower()
                if "duplicate" in msg or "1060" in msg:
                    log.debug("HTTP trace column exists, skip: %s", sql[:72])
                    continue
                log.warning("HTTP trace column migration failed: %s", e)


async def _ensure_history_request_id_columns() -> None:
    """
    create_all 不会给已有表加列；旧库需要补 request_id。
    """
    engine = await mysql_connector.get_engine()
    stmts = [
        "ALTER TABLE image_history_cards ADD COLUMN request_id VARCHAR(36) NULL",
        "ALTER TABLE video_analysis_history ADD COLUMN request_id VARCHAR(36) NULL",
    ]
    async with engine.begin() as conn:
        for sql in stmts:
            try:
                await conn.execute(text(sql))
                log.info("Applied column migration: %s", sql[:72])
            except Exception as e:
                msg = str(e).lower()
                if "duplicate" in msg or "1060" in msg:
                    log.debug("Column already exists, skip: %s", sql[:60])
                    continue
                log.warning("Column migration failed (check DB user permissions): %s", e)


async def _ensure_video_analysis_history_extras() -> None:
    """补全 video_analysis_history 扩展列（create_all 不会改已有表结构）。"""
    engine = await mysql_connector.get_engine()
    stmts = [
        "ALTER TABLE video_analysis_history ADD COLUMN car_model TEXT NULL",
    ]
    async with engine.begin() as conn:
        for sql in stmts:
            try:
                await conn.execute(text(sql))
                log.info("Applied video history column migration: %s", sql[:72])
            except Exception as e:
                msg = str(e).lower()
                if "duplicate" in msg or "1060" in msg:
                    log.debug("Video history column already exists, skip: %s", sql[:60])
                    continue
                log.warning("Video history column migration failed: %s", e)


async def _ensure_image_history_extras() -> None:
    """image_history_cards：本轮运行开始时间（重试时耗时基准）。"""
    engine = await mysql_connector.get_engine()
    stmts = [
        "ALTER TABLE image_history_cards ADD COLUMN current_run_started_at DATETIME(6) NULL",
    ]
    async with engine.begin() as conn:
        for sql in stmts:
            try:
                await conn.execute(text(sql))
                log.info("Applied image history column migration: %s", sql[:72])
            except Exception as e:
                msg = str(e).lower()
                if "duplicate" in msg or "1060" in msg:
                    log.debug("Image history column already exists, skip: %s", sql[:60])
                    continue
                log.warning("Image history column migration failed: %s", e)


async def _ensure_video_match_columns() -> None:
    """新库 create_all 会建列；旧库补 video_match_* 扩展字段。"""
    engine = await mysql_connector.get_engine()
    stmts = [
        "ALTER TABLE video_match_job ADD COLUMN search_status VARCHAR(32) NOT NULL DEFAULT 'pending'",
        "ALTER TABLE video_match_job ADD COLUMN search_total_ms DOUBLE NULL",
        "ALTER TABLE video_match_job ADD COLUMN search_error TEXT NULL",
        "ALTER TABLE video_match_job ADD COLUMN search_strategy_snapshot JSON NULL",
        "ALTER TABLE video_match_shot_row ADD COLUMN match_top_hits_json JSON NULL",
        "ALTER TABLE video_match_shot_row ADD COLUMN match_elapsed_ms DOUBLE NULL",
        "ALTER TABLE video_match_shot_row ADD COLUMN obs_audio_url TEXT NULL",
        "ALTER TABLE video_match_job ADD COLUMN request_id VARCHAR(36) NULL",
        "ALTER TABLE video_match_shot_row ADD COLUMN search_request_id VARCHAR(36) NULL",
    ]
    async with engine.begin() as conn:
        for sql in stmts:
            try:
                await conn.execute(text(sql))
                log.info("Applied video_match column migration: %s", sql[:80])
            except Exception as e:
                msg = str(e).lower()
                if "duplicate" in msg or "1060" in msg:
                    log.debug("video_match column exists, skip: %s", sql[:72])
                    continue
                log.warning("video_match column migration failed: %s", e)


async def _ensure_video_source_upload_cache_transcode_columns() -> None:
    engine = await mysql_connector.get_engine()
    stmts = [
        "ALTER TABLE video_source_upload_cache ADD COLUMN low_res_url TEXT NULL",
        "ALTER TABLE video_source_upload_cache ADD COLUMN high_res_url TEXT NULL",
        "ALTER TABLE video_source_upload_cache ADD COLUMN transcode_status VARCHAR(32) NULL",
        "ALTER TABLE video_source_upload_cache ADD COLUMN transcode_error TEXT NULL",
        "ALTER TABLE video_source_upload_cache ADD COLUMN transcode_started_at DATETIME(6) NULL",
    ]
    async with engine.begin() as conn:
        for sql in stmts:
            try:
                await conn.execute(text(sql))
                log.info("Applied video_source_upload_cache column: %s", sql[:88])
            except Exception as e:
                msg = str(e).lower()
                if "duplicate" in msg or "1060" in msg:
                    log.debug("upload cache column exists, skip: %s", sql[:72])
                    continue
                log.warning("video_source_upload_cache migration failed: %s", e)


async def _ensure_mix_video_overall_time_table() -> None:
    """表建在 ``mix_compose.overall_time_mysql_env`` 指向的库（默认 test / ai_recommend*），与应用主库分离。"""
    from infra.storage.mix_overall_time_mysql import get_mix_overall_time_engine

    ddl = """
    CREATE TABLE IF NOT EXISTS mix_video_overall_time (
      biz_id VARCHAR(64) NOT NULL,
      output_url TEXT NULL,
      PRIMARY KEY (biz_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    try:
        engine = await get_mix_overall_time_engine()
    except Exception as e:
        log.warning("mix_video_overall_time: could not open result DB: %s", e)
        return
    async with engine.begin() as conn:
        try:
            await conn.execute(text(ddl))
            log.info("Ensured mix_video_overall_time on mix result DB (minimal schema).")
        except Exception as e:
            log.warning("mix_video_overall_time ensure failed (create manually if needed): %s", e)
        # 旧版 DDL 曾使用 obs_url；现统一为 output_url
        try:
            await conn.execute(
                text("ALTER TABLE mix_video_overall_time ADD COLUMN output_url TEXT NULL")
            )
            log.info("Added mix_video_overall_time.output_url column (if missing).")
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "1060" in msg:
                pass
            else:
                log.debug("mix_video_overall_time output_url alter: %s", e)
        try:
            await conn.execute(
                text(
                    "UPDATE mix_video_overall_time SET output_url = obs_url "
                    "WHERE (output_url IS NULL OR output_url = '') "
                    "AND obs_url IS NOT NULL AND obs_url != ''"
                )
            )
        except Exception:
            pass


async def create_tables_if_not_exists() -> None:
    """
    Create SQLModel tables if they do not exist.
    Uses the existing async MySQL engine.
    """
    engine = await mysql_connector.get_engine()
    async with engine.begin() as conn:
        log.info("Ensuring SQLModel tables exist...")
        await conn.run_sync(SQLModel.metadata.create_all)
        log.info("SQLModel table check complete.")
    await _ensure_http_request_trace_columns()
    await _ensure_history_request_id_columns()
    await _ensure_video_analysis_history_extras()
    await _ensure_image_history_extras()
    await _ensure_video_match_columns()
    await _ensure_video_source_upload_cache_transcode_columns()
    await _ensure_mix_video_overall_time_table()

