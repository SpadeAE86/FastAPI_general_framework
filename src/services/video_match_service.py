from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, update
from sqlmodel import select

from infra.logging.logger import logger as log
from infra.storage.mysql_connector import mysql_connector
from models.pydantic.model_output_schema.seedtext_script_segments_schema import SeedtextIndexTagsEnvelope
from models.sqlmodel.video_analysis import VideoAnalysisSearchStrategy
from models.sqlmodel.video_match import VideoMatchJob, VideoMatchShotRow
from services.http_request_trace_service import http_request_trace_service
from services.script_match_query_builder import INDEX_NAME
from services.script_match_service import match_script_tags_segments
from services.video_analysis_db_service import video_analysis_db_service
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


def _strip_large_numeric_vectors(obj: Any, *, max_list_len: int = 48) -> Any:
    """
    OpenSearch hybrid / KNN 请求体里的向量动辄数千维；写入 http_request_traces 前替换为占位，
    保留可读的 query 结构与短前缀，避免整条变成无法解析的 utf8 裁剪串。
    注意：业务重试匹配由 match_script_tags_segments(tags_json) 重新构造请求，从不反序列化本条入库体。
    """
    if isinstance(obj, list):
        if len(obj) > max_list_len:
            head_len = min(8, len(obj))
            head = obj[:head_len]
            if head and all(isinstance(x, (int, float)) for x in head):
                return {
                    "_omitted": "numeric_vector",
                    "length": len(obj),
                    "head_preview": [round(float(x), 6) for x in head],
                }
        return [_strip_large_numeric_vectors(x, max_list_len=max_list_len) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _strip_large_numeric_vectors(v, max_list_len=max_list_len) for k, v in obj.items()}
    return obj


def _trace_request_body_for_shot_search(m: Dict[str, Any], **extra: Any) -> Any:
    """分镜检索阶段写入 HTTP trace 的 request_body（已向量压缩 + 字节截断）。"""
    payload: Dict[str, Any] = {
        "index": INDEX_NAME,
        "opensearch_body": m.get("opensearch_body"),
        "search_params": m.get("search_params"),
        "query_text": m.get("query_text"),
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    compact = _strip_large_numeric_vectors(payload)
    return _truncate_for_trace(compact)


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


def _merge_job_constraints_into_segment_tags(
    base: Dict[str, Any],
    *,
    car_model: Optional[str],
    frame_size: Optional[str],
) -> Dict[str, Any]:
    """任务表单约束：写入每镜 tags_json，检索时 frame_size / car_model 参与 bool.filter（AND）。"""
    out = dict(base) if base else {}
    cm = (car_model or "").strip()
    if cm:
        out["car_model"] = cm
    fs = (frame_size or "").strip()
    if fs and fs != "未知":
        out["frame_size"] = fs
    return out


def _best_video_path_from_hits(hits: Any) -> Optional[str]:
    """从检索命中取可播放地址（兼容 video_path / video_url 等列）。"""
    if not isinstance(hits, list):
        return None
    for h in hits:
        if not isinstance(h, dict):
            continue
        for key in ("video_path", "video_url", "url", "obs_video_url"):
            u = str(h.get(key) or "").strip()
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
        u = ""
        for key in ("video_path", "video_url", "url", "obs_video_url"):
            u = str(h.get(key) or "").strip()
            if u:
                break
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


async def _enrich_hits_with_resolved_urls(top_hits: Any, shot_cards_version: str) -> List[Dict[str, Any]]:
    """
    将 OpenSearch 命中里的 history_id 解析为可播放地址并写回各 hit 的 video_path，
    便于落库与 Top5 判定（与 get_job_payload 中的 hydrate 同源逻辑）。
    """
    if not isinstance(top_hits, list) or not top_hits:
        return []
    ver: Any = "v2" if (shot_cards_version or "v1").strip() == "v2" else "v1"
    out: List[Dict[str, Any]] = []
    for h in top_hits:
        if not isinstance(h, dict):
            continue
        nh = dict(h)
        if not str(
            nh.get("video_path", "") or nh.get("video_url", "") or nh.get("url", "") or nh.get("obs_video_url", "") or ""
        ).strip():
            hid = str(nh.get("history_id") or "").strip()
            if hid:
                url = await video_analysis_db_service.resolve_source_video_url_for_index_key(
                    hid, shot_cards_version=ver
                )
                if url:
                    nh["video_path"] = url
        out.append(nh)
    return out


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


async def _hydrate_shot_match_urls_for_response(
    shot: Dict[str, Any],
    *,
    shot_cards_version: str,
) -> None:
    """
    读取任务时补全展示字段：库内 ``top1_obs_url`` 可能因历史 bug 为空，但 ``match_top_hits_json``
    里仍有 ``history_id``。用 ``resolve_source_video_url_for_index_key`` 再解析一次（含纯数字 video 键）。
    """
    if str(shot.get("top1_obs_url") or "").strip():
        return
    if str(shot.get("search_status") or "").lower() != "done":
        return
    hits = shot.get("match_top_hits_json")
    if not isinstance(hits, list) or not hits:
        return
    ver: Any = "v2" if (shot_cards_version or "v1").strip() == "v2" else "v1"
    new_hits: List[Any] = []
    for h in hits:
        if not isinstance(h, dict):
            new_hits.append(h)
            continue
        nh = dict(h)
        if not str(
            nh.get("video_path") or nh.get("video_url") or nh.get("url") or nh.get("obs_video_url") or ""
        ).strip():
            hid = str(nh.get("history_id") or "").strip()
            if hid:
                url = await video_analysis_db_service.resolve_source_video_url_for_index_key(
                    hid, shot_cards_version=ver
                )
                if url:
                    nh["video_path"] = url
        new_hits.append(nh)
    t1 = _best_video_path_from_hits(new_hits)
    if not t1:
        log.debug(
            "video_match hydrate: shot_order={} still no top1 (hits={})",
            shot.get("shot_order"),
            len(new_hits),
        )
        return
    shot["match_top_hits_json"] = new_hits
    shot["top1_obs_url"] = t1
    shot["top5_video_urls"] = _top5_video_urls_from_hits(new_hits)
    shot["match_hit_count"] = len(new_hits)


def _tags_summary_from_json(tj: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("car_model", "frame_size", "subject", "footage_type", "movement", "product_status_scene"):
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
        "script": "",
        "topic": None,
        "title": None,
        "car_model": None,
        "frame_size": None,
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
    ws_ver = "v2" if str(job.workspace or "v1").strip() == "v2" else "v1"
    shots = [shot_row_to_api_dict(r) for r in rows]
    for s in shots:
        await _hydrate_shot_match_urls_for_response(s, shot_cards_version=ws_ver)
    return {
        "success": True,
        "mock": False,
        "job_id": job.id,
        "request_id": job.request_id,
        "script": job.script,
        "topic": job.topic,
        "title": job.title,
        "car_model": job.car_model,
        "frame_size": job.frame_size,
        "parse_status": job.parse_status,
        "parse_error": job.parse_error,
        "workspace": job.workspace,
        "search_status": job.search_status,
        "search_total_ms": job.search_total_ms,
        "search_error": job.search_error,
        "search_strategy_snapshot": job.search_strategy_snapshot,
        "shots": shots,
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
        job_row = await session.get(VideoMatchJob, jid)
        ws_ver = (
            "v2"
            if job_row is not None and str(job_row.workspace or "v1").strip() == "v2"
            else "v1"
        )
        rid = (row.search_request_id or "").strip()
        shot_order = int(row.shot_order)
        seg_text = row.segment_text or ""
        shot_api = shot_row_to_api_dict(row)

    await _hydrate_shot_match_urls_for_response(shot_api, shot_cards_version=ws_ver)

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


async def rematch_video_match_shot(job_id: str, shot_row_id: int) -> Dict[str, Any]:
    """
    单条分镜重新跑 OpenSearch 匹配（需 job 已有 search_strategy_snapshot，通常需先成功跑过整 job 匹配）。
    """
    jid = (job_id or "").strip()
    try:
        sid = int(shot_row_id)
    except (TypeError, ValueError):
        sid = 0
    if not jid or sid <= 0:
        return {"success": False, "error": "invalid id"}

    async with mysql_connector.session_scope() as session:
        job = await session.get(VideoMatchJob, jid)
        if job is None:
            return {"success": False, "error": "job not found"}
        if job.parse_status != "done":
            return {"success": False, "error": "parse not completed"}
        snap = job.search_strategy_snapshot
        if not isinstance(snap, dict) or not str(snap.get("name") or "").strip():
            return {
                "success": False,
                "error": "缺少检索策略快照，请先在视频匹配工作台完成一次整 job 素材匹配",
            }
        strategy_name = str(snap.get("name")).strip()
        row = await session.get(VideoMatchShotRow, sid)
        if row is None or str(row.job_id) != jid:
            return {"success": False, "error": "shot not found"}
        if not (row.tags_json or {}):
            return {"success": False, "error": "分镜缺少标签，无法检索"}
        row.search_status = "running"
        row.search_request_id = None
        row.top1_obs_url = None
        row.match_top_hits_json = None
        row.match_elapsed_ms = None
        session.add(row)
        await session.commit()

        seg = dict(row.tags_json or {})
        ws = (job.workspace or "v1").strip()
        shot_ver = "v2" if ws == "v2" else "v1"

    strategy = await _load_strategy_by_name(strategy_name)
    if strategy is None:
        async with mysql_connector.session_scope() as session:
            row2 = await session.get(VideoMatchShotRow, sid)
            if row2:
                row2.search_status = "failed"
                session.add(row2)
                await session.commit()
        return {"success": False, "error": f"strategy not found: {strategy_name!r}"}

    bw = float(strategy.bm25_weight or 0.3)
    vw = float(strategy.vector_weight or 0.7)
    den = bw + vw or 1.0
    bm25_f = bw / den
    vec_f = vw / den
    mode = "field_aligned_hybrid"
    top_k = 5

    async def persist_one(_idx: int, m: Dict[str, Any]) -> None:
        top_hits_raw = m.get("top_hits") or []
        enriched = await _enrich_hits_with_resolved_urls(top_hits_raw, shot_ver)
        urls5 = _top5_video_urls_from_hits(enriched)
        match_ok = bool(urls5)
        top1 = urls5[0] if urls5 else None
        elapsed = float(m.get("elapsed_ms") or 0)
        body_for_trace = _trace_request_body_for_shot_search(m, rematch_single_shot=True)
        trace_rid = await http_request_trace_service.create_initial(
            request_url=f"/opensearch/{INDEX_NAME}/_search",
            http_method="POST",
            method_name="POST /opensearch/_search",
            business_type="VIDEO_MATCH_SHOT_SEARCH",
            business_id=str(sid),
            upstream_task_id=jid,
            request_body=body_for_trace,
        )
        try:
            async with mysql_connector.session_scope() as session:
                db_row = await session.get(VideoMatchShotRow, sid)
                if db_row is None:
                    await http_request_trace_service.finalize(
                        trace_rid,
                        status_code=500,
                        error_message="shot row missing after search",
                        business_success=False,
                    )
                    return
                db_row.match_top_hits_json = enriched
                db_row.match_elapsed_ms = elapsed
                db_row.search_status = "done" if match_ok else "failed"
                db_row.top1_obs_url = top1
                db_row.search_request_id = trace_rid
                session.add(db_row)
                await session.commit()
        except Exception:
            log.exception("video_match rematch persist DB failed job={} row={}", jid, sid)
            await http_request_trace_service.finalize(
                trace_rid,
                status_code=500,
                error_message="persist rematch database error",
                business_success=False,
            )
            raise

        shot_ord = 0
        async with mysql_connector.session_scope() as session:
            rord = await session.get(VideoMatchShotRow, sid)
            if rord is not None:
                shot_ord = int(rord.shot_order)
        resp_summary = {
            "hit_count": len(top_hits_raw),
            "top_history_ids": [h.get("history_id") for h in top_hits_raw[:5]],
            "elapsed_ms": elapsed,
            "shot_order": shot_ord,
            "rematch": True,
            "match_ok": match_ok,
            "top5_nonempty": match_ok,
        }
        await http_request_trace_service.finalize(
            trace_rid,
            status_code=200,
            response_body=resp_summary,
            business_success=match_ok,
            duration_ms=int(elapsed) if elapsed else None,
        )
        log.info(
            "video_match shot_search rematch job={} shot_order={} row_id={} hit_count={} match_ok={} top1={} top5_urls={} elapsed_ms={}",
            jid,
            shot_ord,
            sid,
            len(top_hits_raw),
            match_ok,
            top1,
            urls5,
            elapsed,
        )

    try:
        await match_script_tags_segments(
            [seg],
            top_k=int(top_k),
            mode=mode,
            shot_cards_version=shot_ver,
            concurrency=1,
            bm25_factor=bm25_f,
            vector_factor=vec_f,
            use_rrf=bool(strategy.use_rrf),
            with_timings=True,
            on_segment_done=persist_one,
        )
    except Exception as e:
        log.exception("video_match rematch shot failed: {}", e)
        async with mysql_connector.session_scope() as session:
            row3 = await session.get(VideoMatchShotRow, sid)
            if row3:
                row3.search_status = "failed"
                session.add(row3)
                await session.commit()
        return {"success": False, "error": str(e)}

    out = await get_shot_match_detail(jid, sid)
    if out:
        shot = out.get("shot")
        if isinstance(shot, dict) and (shot.get("search_status") or "").lower() == "failed":
            out["success"] = False
            out["error"] = "本分镜无有效素材命中（Top5 为空或无法解析视频地址）"
        return out
    return {"success": False, "error": "rematch ok but failed to load shot detail"}


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
            "video_match search: strategy {} has field-level weights; script_match uses macro bm25/vector only for now",
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
        # 整 job 重跑匹配：所有分镜进入「匹配中」，并清空上轮结果，避免前端仍显示旧 Top5/成功态
        for r in rows:
            r.search_status = "running"
            r.top1_obs_url = None
            r.match_top_hits_json = None
            r.match_elapsed_ms = None
            r.search_request_id = None
            session.add(r)
        session.add(job)
        await session.commit()

    log.info(
        "video_match search start job={} shot_count={} strategy={} top_k={} shot_cards_version={}",
        job_id,
        len(rows),
        strategy_name,
        top_k,
        shot_ver,
    )

    segments = [dict(r.tags_json or {}) for r in rows]

    async def persist_shot(idx: int, m: Dict[str, Any]) -> None:
        if idx < 0 or idx >= len(row_ids):
            return
        row_id = row_ids[idx]
        shot_ord = rows[idx].shot_order
        top_hits_raw = m.get("top_hits") or []
        enriched = await _enrich_hits_with_resolved_urls(top_hits_raw, shot_ver)
        urls5 = _top5_video_urls_from_hits(enriched)
        match_ok = bool(urls5)
        top1 = urls5[0] if urls5 else None
        elapsed = float(m.get("elapsed_ms") or 0)

        body_for_trace = _trace_request_body_for_shot_search(m)
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
                row.match_top_hits_json = enriched
                row.match_elapsed_ms = elapsed
                row.search_status = "done" if match_ok else "failed"
                row.top1_obs_url = top1
                row.search_request_id = trace_rid
                session.add(row)
                await session.commit()
        except Exception:
            log.exception("video_match persist_shot DB failed job={} row={}", job_id, row_id)
            await http_request_trace_service.finalize(
                trace_rid,
                status_code=500,
                error_message="persist_shot database error",
                business_success=False,
            )
            raise

        resp_summary = {
            "hit_count": len(top_hits_raw),
            "top_history_ids": [h.get("history_id") for h in top_hits_raw[:5]],
            "elapsed_ms": elapsed,
            "shot_order": shot_ord,
            "match_ok": match_ok,
            "top5_nonempty": match_ok,
        }
        await http_request_trace_service.finalize(
            trace_rid,
            status_code=200,
            response_body=resp_summary,
            business_success=match_ok,
            duration_ms=int(elapsed) if elapsed else None,
        )
        log.info(
            "video_match shot_search job={} shot_order={} row_id={} hit_count={} match_ok={} top1={} top5_urls={} elapsed_ms={}",
            job_id,
            shot_ord,
            row_id,
            len(top_hits_raw),
            match_ok,
            top1,
            urls5,
            elapsed,
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
        log.exception("video_match search failed: {}", e)
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
        log.warning("video_match: match count {} != rows {}", len(matches), len(rows))

    log.info("video_match search finished job={} wall_ms={} segments={}", job_id, total_ms, len(rows))

    async with mysql_connector.session_scope() as session:
        job = await session.get(VideoMatchJob, job_id)
        res_sr = await session.execute(
            select(VideoMatchShotRow).where(VideoMatchShotRow.job_id == job_id)
        )
        shot_rows = list(res_sr.scalars().all())
        n_fail = sum(1 for sr in shot_rows if (sr.search_status or "").lower() == "failed")
        if job:
            if n_fail:
                job.search_status = "failed"
                job.search_error = (
                    f"{n_fail} 条分镜素材匹配失败（无 OpenSearch 命中或无法解析出有效视频地址 / Top5 为空）"
                )
            else:
                job.search_status = "done"
                job.search_error = None
            job.search_total_ms = total_ms
            session.add(job)
        await session.commit()

    out = await get_job_payload(job_id)
    if out is None:
        return {"success": False, "error": "job not found after search"}
    job_failed = (out.get("search_status") or "").lower() == "failed"
    out["success"] = not job_failed
    if job_failed:
        out["error"] = out.get("search_error") or "部分或全部分镜匹配失败"
    out["search_total_ms"] = total_ms
    return out


async def create_job_and_parse(
    *,
    script: str,
    topic: Optional[str] = None,
    title: Optional[str] = None,
    car_model: Optional[str] = None,
    frame_size: Optional[str] = None,
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

    fs_norm = (frame_size or "").strip() or None

    async with mysql_connector.session_scope() as session:
        session.add(
            VideoMatchJob(
                id=job_id,
                workspace=ws,
                script=script,
                topic=topic.strip() if topic else None,
                title=title.strip() if title else None,
                car_model=car_model.strip() if car_model else None,
                frame_size=fs_norm,
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
                "frame_size": fs_norm,
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
        log.exception("video_match parse rewrite failed: {}", e)
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
            tj = _merge_job_constraints_into_segment_tags(
                tj,
                car_model=car_model,
                frame_size=fs_norm,
            )
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
                "frame_size": j.frame_size,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "updated_at": j.updated_at.isoformat() if j.updated_at else None,
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
        log.exception("synthesize_shot_obs_audio: TTS failed job={} shot={}", jid, shot_row_id)
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


async def mark_interrupted_video_match_jobs_failed(reason: str) -> int:
    """进程重启后：口播解析 / 素材检索仍为进行中的 job 标为失败（search 的 pending 表示未发起匹配，不处理）。"""
    msg = (reason or "").strip() or "interrupted"
    n = 0
    async with mysql_connector.session_scope() as session:
        res_p = await session.execute(
            update(VideoMatchJob)
            .where(
                func.lower(func.coalesce(VideoMatchJob.parse_status, "")).in_(
                    ["running", "pending", "processing"]
                )
            )
            .values(parse_status="failed", parse_error=msg)
        )
        n += int(res_p.rowcount or 0)
        res_s = await session.execute(
            update(VideoMatchJob)
            .where(
                func.lower(func.coalesce(VideoMatchJob.search_status, "")).in_(["running", "processing"])
            )
            .values(search_status="failed", search_error=msg)
        )
        n += int(res_s.rowcount or 0)
        await session.commit()
    return n


async def schedule_video_match_job_retry(job_id: str) -> Dict[str, Any]:
    """
    校验失败任务并占用状态（解析重试会清空分镜行）。
    返回 { success, kind: 'parse'|'search', strategy_name? }。
    """
    jid = (job_id or "").strip()
    if not jid:
        return {"success": False, "error": "invalid job_id"}
    async with mysql_connector.session_scope() as session:
        job = await session.get(VideoMatchJob, jid)
        if job is None:
            return {"success": False, "error": "job not found"}
        ps = (job.parse_status or "").lower()
        ss = (job.search_status or "").lower()
        if ps == "running" or ss == "running" or ps == "processing" or ss == "processing":
            return {"success": False, "error": "任务仍在执行中，请稍后再试"}
        if ps == "failed":
            await session.execute(delete(VideoMatchShotRow).where(VideoMatchShotRow.job_id == jid))
            job.parse_status = "running"
            job.parse_error = None
            job.search_status = "pending"
            job.search_error = None
            job.search_total_ms = None
            job.search_strategy_snapshot = None
            session.add(job)
            await session.commit()
            return {"success": True, "kind": "parse"}
        if ps == "done" and ss == "failed":
            snap = job.search_strategy_snapshot
            name = ""
            if isinstance(snap, dict):
                raw = snap.get("name")
                name = str(raw).strip() if raw else ""
            if not name:
                return {
                    "success": False,
                    "error": "缺少历史检索策略，请先在视频匹配页成功发起过一次检索后再重试",
                }
            job.search_status = "running"
            job.search_error = None
            session.add(job)
            await session.commit()
            return {"success": True, "kind": "search", "strategy_name": name}
        return {"success": False, "error": "仅口播转写失败或素材检索失败的任务可重试"}


async def run_video_match_retry_background(
    job_id: str, kind: str, strategy_name: Optional[str] = None
) -> None:
    jid = (job_id or "").strip()
    k = (kind or "").strip()
    try:
        if k == "parse":
            await _reparse_video_match_job_core(jid)
        elif k == "search" and (strategy_name or "").strip():
            await run_job_search(
                jid,
                strategy_name=str(strategy_name).strip(),
                mode="field_aligned_hybrid",
                top_k=5,
            )
        else:
            log.error("video_match retry worker: bad args job={} kind={}", jid, k)
    except Exception:
        log.exception("video_match retry background failed job={}", jid)


async def _reparse_video_match_job_core(job_id: str) -> None:
    """假定 job 已 parse_status=running 且分镜行已清空；执行 LLM 转写并落库。"""
    jid = (job_id or "").strip()
    if not jid:
        return
    async with mysql_connector.session_scope() as session:
        job0 = await session.get(VideoMatchJob, jid)
        if job0 is None:
            return
        script = (job0.script or "").strip()
        topic = job0.topic
        title = job0.title
        car_model = job0.car_model
        frame_size_job = (job0.frame_size or "").strip() or None
        ws = (job0.workspace or "v1").strip() or "v1"
    if not script:
        async with mysql_connector.session_scope() as session:
            jbad = await session.get(VideoMatchJob, jid)
            if jbad:
                jbad.parse_status = "failed"
                jbad.parse_error = "script is empty"
                session.add(jbad)
                await session.commit()
        return

    parse_rid = await http_request_trace_service.create_initial(
        request_url="/internal/video-match/parse-retry",
        http_method="POST",
        method_name="POST /video-match/jobs/{id}/retry",
        business_type="VIDEO_MATCH_PARSE",
        business_id=jid,
        upstream_task_id=jid,
        request_body=_truncate_for_trace(
            {
                "job_id": jid,
                "workspace": ws,
                "retry": True,
                "script_preview": script[:8000],
                "car_model": car_model,
                "frame_size": frame_size_job,
            },
            max_bytes=32000,
        ),
    )
    async with mysql_connector.session_scope() as session:
        job_link = await session.get(VideoMatchJob, jid)
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
            tts_obs_project_id=jid,
            out_obs_audio_urls=tts_audio_urls,
        )
    except Exception as e:
        log.exception("video_match parse retry failed: {}", e)
        await http_request_trace_service.finalize(
            parse_rid,
            status_code=500,
            error_message=str(e)[:2000],
            response_body={"parse_status": "failed"},
            business_success=False,
            duration_ms=int((time.perf_counter() - t_parse0) * 1000),
        )
        async with mysql_connector.session_scope() as session:
            job = await session.get(VideoMatchJob, jid)
            if job:
                job.parse_status = "failed"
                job.parse_error = str(e)
                session.add(job)
                await session.commit()
        return

    async with mysql_connector.session_scope() as session:
        for order, seg in enumerate(storyboard.storyboard):
            tag_seg = _resolve_tag_segment(tags, seg.id, order)
            tj: Optional[Dict[str, Any]]
            if tag_seg is not None:
                tj = tag_seg.model_dump(exclude_none=True)
            else:
                tj = {}
            tj = _merge_job_constraints_into_segment_tags(
                tj,
                car_model=car_model,
                frame_size=frame_size_job,
            )
            obs_url = tts_audio_urls[order] if order < len(tts_audio_urls) else None
            row = VideoMatchShotRow(
                job_id=jid,
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
        job = await session.get(VideoMatchJob, jid)
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
            "retry": True,
        },
        business_success=True,
        duration_ms=int((time.perf_counter() - t_parse0) * 1000),
    )
