from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlmodel import select

from infra.logging.logger import logger as log
from infra.storage.mysql_connector import mysql_connector
from models.pydantic.model_output_schema.seedtext_script_segments_schema import SeedtextIndexTagsEnvelope
from models.sqlmodel.video_analysis import VideoAnalysisSearchStrategy
from models.sqlmodel.video_match import VideoMatchJob, VideoMatchShotRow
from services.http_request_trace_service import http_request_trace_service
from services.script_match_query_builder import INDEX_NAME
from services.script_match_service import match_script_tags_segments
from services.script_rewrite_service import (
    rewrite_script_to_storyboard_and_tags,
    synthesize_text_to_obs_wav,
)

# 后续「每分镜 OpenSearch 匹配」时在此使用 asyncio.Semaphore 限制并发
MATCH_CONCURRENCY = 4


def _truncate_for_trace(obj: Any, max_bytes: int = 28000) -> Any:
    """避免 request_body 撑爆 JSON 列；尽量保留结构，超长时改为预览字符串。"""
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return {"_error": "non_json_serializable"}
    b = s.encode("utf-8")
    if len(b) <= max_bytes:
        return obj
    cut = max_bytes - 120
    pref = s[:cut] if cut > 0 else ""
    return {"_truncated": True, "utf8_preview": pref + "…"}


def _tags_by_seg_id(tags: SeedtextIndexTagsEnvelope) -> Dict[int, Any]:
    return {seg.id: seg for seg in tags.segment_result}


def _resolve_tag_segment(
    tags: SeedtextIndexTagsEnvelope,
      storyboard_seg_id: int,
      order: int,
):
    by_id = _tags_by_seg_id(tags)
    if storyboard_seg_id in by_id:
        return by_id[storyboard_seg_id]
    if order < len(tags.segment_result):
        return tags.segment_result[order]
    return None


def _best_video_path_from_hits(hits: Any) -> Optional[str]:
    """按检索排序取第一个能解析到 OBS 的命中（避免 Top1 文档无 video_url 时整行显示为 —）。"""
    if not isinstance(hits, list):
        return None
    for h in hits:
        if not isinstance(h, dict):
            continue
        u = str(h.get("video_path") or "").strip()
        if u:
            return u
    return None


def _top5_video_urls_from_hits(hits: Any) -> List[str]:
    if not isinstance(hits, list):
        return []
    urls: List[str] = []
    seen: set[str] = set()
    for h in hits:
        if len(urls) >= 5:
            break
        if not isinstance(h, dict):
            continue
        u = str(h.get("video_path") or "").strip()
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def shot_row_to_api_dict(row: VideoMatchShotRow) -> Dict[str, Any]:
    tj = row.tags_json or {}
    summary = _tags_summary_from_json(tj)
    hits = row.match_top_hits_json
    stored_top1 = str(row.top1_obs_url or "").strip() or None
    fallback_top1 = _best_video_path_from_hits(hits)
    top1_effective = fallback_top1 or stored_top1
    return {
        "id": row.id,
        "shot_order": row.shot_order,
        "storyboard_id": row.storyboard_id,
        "segment_text": row.segment_text,
        "duration_sec": row.duration_sec,
        "description": row.description,
        "tags_summary": summary,
        "tags_json": tj,
        "search_status": row.search_status,
        "top1_obs_url": top1_effective,
        "top5_video_urls": _top5_video_urls_from_hits(hits),
        "obs_audio_url": row.obs_audio_url,
        "match_top_hits_json": row.match_top_hits_json,
        "match_elapsed_ms": row.match_elapsed_ms,
        "match_hit_count": len(hits) if isinstance(hits, list) else 0,
        "search_request_id": row.search_request_id,
    }


def _tags_summary_from_json(tj: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("subject", "footage_type", "movement", "product_status_scene"):
        v = tj.get(key)
        if v and isinstance(v, str) and v.strip() and v != "未知":
            parts.append(v.strip())
    objs = tj.get("object")
    if isinstance(objs, list):
        parts.extend(str(x) for x in objs[:3] if x)
    return " · ".join(parts[:8]) if parts else "—"


def _mock_response_payload() -> Dict[str, Any]:
    """与真实 parse 成功时相同 schema，便于前端联调。"""
    shots = [
        {
            "id": None,
            "shot_order": 0,
            "storyboard_id": 1,
            "segment_text": "同级唯一，全系标配大厂底盘。",
            "duration_sec": 2.4,
            "description": "城市道路跟拍，车身平稳，强调底盘质感。",
            "tags_summary": "",
            "tags_json": {
                "id": 1,
                "segment_text": "同级唯一，全系标配大厂底盘。",
                "duration": 2.4,
                "description": "跟拍路跑，侧向航拍交代环境",
                "movement": "行驶",
                "subject": "智己LS6",
                "footage_type": "生活实拍",
                "product_status_scene": "动态路跑",
                "object": ["四轮", "城市道路"],
                "scene_location": ["城市道路"],
            },
            "search_status": "pending",
            "top1_obs_url": None,
            "top5_video_urls": [],
            "obs_audio_url": None,
            "match_top_hits_json": None,
            "match_elapsed_ms": None,
            "match_hit_count": 0,
            "search_request_id": None,
        },
        {
            "id": None,
            "shot_order": 1,
            "storyboard_id": 2,
            "segment_text": "一键 AI 泊车，地库自己找车位。",
            "duration_sec": 3.0,
            "description": "车内 POV，中控显示泊车界面，地库环境。",
            "tags_summary": "",
            "tags_json": {
                "id": 2,
                "segment_text": "一键 AI 泊车，地库自己找车位。",
                "duration": 3.0,
                "description": "中控大屏与方向盘入画，泊车 UI",
                "movement": "静止",
                "subject": "中控大屏",
                "footage_type": "生活实拍",
                "product_status_scene": "功能演示",
                "object": ["方向盘", "地库"],
                "scene_location": ["地库"],
            },
            "search_status": "pending",
            "top1_obs_url": None,
            "top5_video_urls": [],
            "obs_audio_url": None,
            "match_top_hits_json": None,
            "match_elapsed_ms": None,
            "match_hit_count": 0,
            "search_request_id": None,
        },
        {
            "id": None,
            "shot_order": 2,
            "storyboard_id": 3,
            "segment_text": "静谧座舱，长途也不累。",
            "duration_sec": 2.0,
            "description": "后排乘坐空间与氛围光，安静体感。",
            "tags_summary": "",
            "tags_json": {
                "id": 3,
                "segment_text": "静谧座舱，长途也不累。",
                "duration": 2.0,
                "description": "后排座椅与车窗取景",
                "movement": "静止",
                "subject": "后排座椅",
                "footage_type": "TVC切片",
                "product_status_scene": "静态内饰",
                "object": ["氛围灯"],
                "scene_location": ["车内"],
            },
            "search_status": "pending",
            "top1_obs_url": None,
            "top5_video_urls": [],
            "obs_audio_url": None,
            "match_top_hits_json": None,
            "match_elapsed_ms": None,
            "match_hit_count": 0,
            "search_request_id": None,
        },
    ]
    for s in shots:
        s["tags_summary"] = _tags_summary_from_json(s["tags_json"])
    return {
        "success": True,
        "mock": True,
        "job_id": "00000000-0000-0000-0000-00000000mock",
        "request_id": None,
        "parse_status": "done",
        "search_status": "pending",
        "search_total_ms": None,
        "search_error": None,
        "search_strategy_snapshot": None,
        "shots": shots,
    }


async def get_job_payload(job_id: str) -> Optional[Dict[str, Any]]:
    async with mysql_connector.session_scope() as session:
        job = await session.get(VideoMatchJob, job_id)
        if job is None:
            return None
        res = await session.execute(
            select(VideoMatchShotRow)
            .where(VideoMatchShotRow.job_id == job_id)
            .order_by(VideoMatchShotRow.shot_order)
        )
        rows = list(res.scalars().all())
    return {
        "success": True,
        "mock": False,
        "job_id": job.id,
        "request_id": job.request_id,
        "parse_status": job.parse_status,
        "parse_error": job.parse_error,
        "workspace": job.workspace,
        "search_status": job.search_status,
        "search_total_ms": job.search_total_ms,
        "search_error": job.search_error,
        "search_strategy_snapshot": job.search_strategy_snapshot,
        "shots": [shot_row_to_api_dict(r) for r in rows],
    }


async def get_shot_match_detail(job_id: str, shot_row_id: int) -> Optional[Dict[str, Any]]:
    """分镜「素材匹配」阶段详情：合并 http_request_traces（search_request_id）。"""
    jid = (job_id or "").strip()
    if not jid or shot_row_id <= 0:
        return None
    from services.task_detail_service import (
        build_video_match_shot_search_task_detail,
        merge_http_trace_into_detail,
    )

    async with mysql_connector.session_scope() as session:
        row = await session.get(VideoMatchShotRow, shot_row_id)
        if row is None or str(row.job_id) != jid:
            return None
        rid = (row.search_request_id or "").strip()
        shot_order = int(row.shot_order)
        seg_text = row.segment_text or ""
        shot_api = shot_row_to_api_dict(row)

    base = build_video_match_shot_search_task_detail(
        job_id=jid,
        shot_row_id=shot_row_id,
        shot_order=shot_order,
        segment_text_preview=seg_text,
        opensearch_index=INDEX_NAME,
    )
    trace = await http_request_trace_service.get_dict(rid) if rid else None
    detail = merge_http_trace_into_detail(base, trace)
    return {"success": True, "detail": detail, "shot": shot_api}


async def _load_strategy_by_name(name: str) -> Optional[VideoAnalysisSearchStrategy]:
    n = (name or "").strip()
    if not n:
        return None
    async with mysql_connector.session_scope() as session:
        res = await session.execute(
            select(VideoAnalysisSearchStrategy).where(VideoAnalysisSearchStrategy.name == n)
        )
        return res.scalars().first()


async def run_job_search(
    job_id: str,
    *,
    strategy_name: str,
    mode: str = "field_aligned_hybrid",
    top_k: int = 5,
) -> Dict[str, Any]:
    strategy_name = (strategy_name or "").strip()
    if not strategy_name:
        return {"success": False, "error": "strategy_name is required"}

    strategy = await _load_strategy_by_name(strategy_name)
    if strategy is None:
        return {"success": False, "error": f"strategy not found: {strategy_name!r}"}

    bw = float(strategy.bm25_weight or 0.3)
    vw = float(strategy.vector_weight or 0.7)
    den = bw + vw or 1.0
    bm25_f = bw / den
    vec_f = vw / den

    snapshot: Dict[str, Any] = {
        "name": strategy.name,
        "use_rrf": bool(strategy.use_rrf),
        "bm25_weight": strategy.bm25_weight,
        "vector_weight": strategy.vector_weight,
        "text_weights": strategy.text_weights,
        "vector_weights": strategy.vector_weights,
    }
    if strategy.text_weights or strategy.vector_weights:
        log.info(
            "video_match search: strategy %r has field-level weights; script_match uses macro bm25/vector only for now",
            strategy.name,
        )

    row_ids: List[int] = []
    shot_ver = "v1"
    rows: List[VideoMatchShotRow] = []

    async with mysql_connector.session_scope() as session:
        job = await session.get(VideoMatchJob, job_id)
        if job is None:
            return {"success": False, "error": "job not found"}
        if job.parse_status != "done":
            return {"success": False, "error": "parse not completed"}
        res = await session.execute(
            select(VideoMatchShotRow)
            .where(VideoMatchShotRow.job_id == job_id)
            .order_by(VideoMatchShotRow.shot_order)
        )
        rows = list(res.scalars().all())
        if not rows:
            return {"success": False, "error": "no shot rows"}
        for r in rows:
            if not (r.tags_json or {}):
                return {"success": False, "error": f"shot_order={r.shot_order} missing tags_json"}
        missing_ids = [r for r in rows if r.id is None]
        if missing_ids:
            return {"success": False, "error": "shot rows missing ids (database error)"}

        row_ids = [int(r.id) for r in rows]
        ws = (job.workspace or "v1").strip()
        shot_ver = "v2" if ws == "v2" else "v1"

        job.search_status = "running"
        job.search_error = None
        job.search_strategy_snapshot = snapshot
        session.add(job)
        await session.commit()

    segments = [dict(r.tags_json or {}) for r in rows]

    async def persist_shot(idx: int, m: Dict[str, Any]) -> None:
        if idx < 0 or idx >= len(row_ids):
            return
        row_id = row_ids[idx]
        shot_ord = rows[idx].shot_order
        top_hits = m.get("top_hits") or []
        elapsed = float(m.get("elapsed_ms") or 0)
        top1 = _best_video_path_from_hits(top_hits)

        body_for_trace = _truncate_for_trace(
            {
                "index": INDEX_NAME,
                "opensearch_body": m.get("opensearch_body"),
                "search_params": m.get("search_params"),
                "query_text": m.get("query_text"),
            }
        )
        trace_rid = await http_request_trace_service.create_initial(
            request_url=f"/opensearch/{INDEX_NAME}/_search",
            http_method="POST",
            method_name="POST /opensearch/_search",
            business_type="VIDEO_MATCH_SHOT_SEARCH",
            business_id=str(row_id),
            upstream_task_id=job_id,
            request_body=body_for_trace,
        )
        try:
            async with mysql_connector.session_scope() as session:
                row = await session.get(VideoMatchShotRow, row_id)
                if row is None:
                    await http_request_trace_service.finalize(
                        trace_rid,
                        status_code=500,
                        error_message="shot row missing after search",
                        business_success=False,
                    )
                    return
                row.match_top_hits_json = top_hits
                row.match_elapsed_ms = elapsed
                row.search_status = "done"
                row.top1_obs_url = top1
                row.search_request_id = trace_rid
                session.add(row)
                await session.commit()
        except Exception:
            log.exception("video_match persist_shot DB failed job=%s row=%s", job_id, row_id)
            await http_request_trace_service.finalize(
                trace_rid,
                status_code=500,
                error_message="persist_shot database error",
                business_success=False,
            )
            raise

        resp_summary = {
            "hit_count": len(top_hits),
            "top_history_ids": [h.get("history_id") for h in top_hits[:5]],
            "elapsed_ms": elapsed,
            "shot_order": shot_ord,
        }
        await http_request_trace_service.finalize(
            trace_rid,
            status_code=200,
            response_body=resp_summary,
            business_success=True,
            duration_ms=int(elapsed) if elapsed else None,
        )

    t_wall0 = time.perf_counter()
    try:
        matches = await match_script_tags_segments(
            segments,
            top_k=int(top_k),
            mode=mode,
            shot_cards_version=shot_ver,
            concurrency=MATCH_CONCURRENCY,
            bm25_factor=bm25_f,
            vector_factor=vec_f,
            use_rrf=bool(strategy.use_rrf),
            with_timings=True,
            on_segment_done=persist_shot,
        )
    except Exception as e:
        log.exception("video_match search failed: %s", e)
        async with mysql_connector.session_scope() as session:
            job = await session.get(VideoMatchJob, job_id)
            if job:
                job.search_status = "failed"
                job.search_error = str(e)
                session.add(job)
                await session.commit()
        return {"success": False, "job_id": job_id, "error": str(e)}

    total_ms = round((time.perf_counter() - t_wall0) * 1000, 3)

    if len(matches) != len(rows):
        log.warning("video_match: match count %s != rows %s", len(matches), len(rows))

    async with mysql_connector.session_scope() as session:
        job = await session.get(VideoMatchJob, job_id)
        if job:
            job.search_status = "done"
            job.search_total_ms = total_ms
            job.search_error = None
            session.add(job)
        await session.commit()

    out = await get_job_payload(job_id)
    if out is None:
        return {"success": False, "error": "job not found after search"}
    out["success"] = True
    out["search_total_ms"] = total_ms
    return out


async def create_job_and_parse(
    *,
    script: str,
    topic: Optional[str] = None,
    title: Optional[str] = None,
    car_model: Optional[str] = None,
    workspace: Optional[str] = "v1",
    mock: bool = False,
) -> Dict[str, Any]:
    if mock:
        return _mock_response_payload()

    script = (script or "").strip()
    if not script:
        return {"success": False, "error": "script cannot be empty"}

    job_id = str(uuid.uuid4())
    ws = (workspace or "v1").strip() or "v1"

    async with mysql_connector.session_scope() as session:
        session.add(
            VideoMatchJob(
                id=job_id,
                workspace=ws,
                script=script,
                topic=topic.strip() if topic else None,
                title=title.strip() if title else None,
                car_model=car_model.strip() if car_model else None,
                parse_status="running",
            )
        )
        await session.commit()

    parse_rid = await http_request_trace_service.create_initial(
        request_url="/internal/video-match/parse",
        http_method="POST",
        method_name="POST /video-match/jobs",
        business_type="VIDEO_MATCH_PARSE",
        business_id=job_id,
        upstream_task_id=job_id,
        request_body=_truncate_for_trace(
            {
                "job_id": job_id,
                "workspace": ws,
                "script_preview": script[:8000],
                "topic": topic,
                "title": title,
                "car_model": car_model,
            },
            max_bytes=32000,
        ),
    )
    async with mysql_connector.session_scope() as session:
        job_link = await session.get(VideoMatchJob, job_id)
        if job_link:
            job_link.request_id = parse_rid
            session.add(job_link)
            await session.commit()

    t_parse0 = time.perf_counter()
    try:
        tts_audio_urls: List[Optional[str]] = []
        storyboard, tags = await rewrite_script_to_storyboard_and_tags(
            script,
            topic=topic,
            title=title,
            car_model=car_model,
            index=0,
            tts_obs_project_id=job_id,
            out_obs_audio_urls=tts_audio_urls,
        )
    except Exception as e:
        log.exception("video_match parse rewrite failed: %s", e)
        await http_request_trace_service.finalize(
            parse_rid,
            status_code=500,
            error_message=str(e)[:2000],
            response_body={"parse_status": "failed"},
            business_success=False,
            duration_ms=int((time.perf_counter() - t_parse0) * 1000),
        )
        async with mysql_connector.session_scope() as session:
            job = await session.get(VideoMatchJob, job_id)
            if job:
                job.parse_status = "failed"
                job.parse_error = str(e)
                session.add(job)
                await session.commit()
        return {"success": False, "job_id": job_id, "error": str(e)}

    async with mysql_connector.session_scope() as session:
        for order, seg in enumerate(storyboard.storyboard):
            tag_seg = _resolve_tag_segment(tags, seg.id, order)
            tj: Optional[Dict[str, Any]]
            if tag_seg is not None:
                tj = tag_seg.model_dump(exclude_none=True)
            else:
                tj = {}
            obs_url = tts_audio_urls[order] if order < len(tts_audio_urls) else None
            row = VideoMatchShotRow(
                job_id=job_id,
                shot_order=order,
                storyboard_id=int(seg.id),
                segment_text=seg.segment_text,
                duration_sec=float(seg.duration),
                description=seg.description,
                tags_json=tj if tj else None,
                search_status="pending",
                obs_audio_url=obs_url,
            )
            session.add(row)
        job = await session.get(VideoMatchJob, job_id)
        if job:
            job.parse_status = "done"
            job.parse_error = None
            session.add(job)
        await session.commit()

    await http_request_trace_service.finalize(
        parse_rid,
        status_code=200,
        response_body={
            "parse_status": "done",
            "shot_count": len(storyboard.storyboard),
        },
        business_success=True,
        duration_ms=int((time.perf_counter() - t_parse0) * 1000),
    )

    loaded = await get_job_payload(job_id)
    if loaded is None:
        return {"success": False, "job_id": job_id, "error": "job not found after parse"}
    return loaded


async def list_video_match_jobs(
    *,
    parse_status: Optional[str] = None,
    workspace: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Lightweight job list for debugging / history picker（如「已转写」会话）。
    """
    lim = max(1, min(int(limit or 50), 100))
    async with mysql_connector.session_scope() as session:
        stmt = select(VideoMatchJob).order_by(VideoMatchJob.created_at.desc()).limit(lim)
        ps = (parse_status or "").strip()
        if ps:
            stmt = stmt.where(VideoMatchJob.parse_status == ps)
        ws = (workspace or "").strip()
        if ws:
            stmt = stmt.where(VideoMatchJob.workspace == ws)
        res = await session.execute(stmt)
        jobs = list(res.scalars().all())
    items: List[Dict[str, Any]] = []
    for j in jobs:
        items.append(
            {
                "id": j.id,
                "workspace": j.workspace,
                "parse_status": j.parse_status,
                "search_status": j.search_status,
                "title": j.title,
                "topic": j.topic,
                "car_model": j.car_model,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "request_id": j.request_id,
            }
        )
    return {"success": True, "jobs": items}


async def synthesize_shot_obs_audio(job_id: str, shot_row_id: int) -> Dict[str, Any]:
    """为单条分镜生成阿里云 TTS、上传 OBS，并写入 ``obs_audio_url``（可选更新 ``duration_sec``）。"""
    jid = (job_id or "").strip()
    if not jid:
        return {"success": False, "error": "invalid job_id"}
    if shot_row_id <= 0:
        return {"success": False, "error": "invalid shot_row_id"}

    async with mysql_connector.session_scope() as session:
        row = await session.get(VideoMatchShotRow, shot_row_id)
        if row is None or str(row.job_id) != jid:
            return {"success": False, "error": "shot not found"}
        segment = (row.segment_text or "").strip()
        if not segment:
            return {"success": False, "error": "segment_text is empty"}
        order_hint = int(row.shot_order)

    try:
        url, dur = await synthesize_text_to_obs_wav(
            segment,
            obs_project_id=jid,
            tts_tid_suffix=f"s{shot_row_id}_{order_hint}",
        )
    except Exception as e:
        log.exception("synthesize_shot_obs_audio: TTS failed job=%s shot=%s", jid, shot_row_id)
        return {"success": False, "error": str(e)}

    if not url:
        return {"success": False, "error": "TTS or OBS upload returned empty URL"}

    async with mysql_connector.session_scope() as session:
        row2 = await session.get(VideoMatchShotRow, shot_row_id)
        if row2 is None or str(row2.job_id) != jid:
            return {"success": False, "error": "shot not found after synthesis"}
        row2.obs_audio_url = url
        if dur is not None:
            row2.duration_sec = float(dur)
        session.add(row2)
        await session.commit()
        payload = shot_row_to_api_dict(row2)

    return {"success": True, "shot": payload}
