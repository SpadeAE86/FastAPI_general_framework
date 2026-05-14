"""进程启动时统一将「进行中」任务标为失败，便于看板与重试入口对齐各业务 history 表。"""

from __future__ import annotations

from typing import Dict

from infra.logging.logger import logger as log


async def mark_interrupted_tasks_on_startup(reason: str) -> Dict[str, int]:
    """
    各表独立实现具体 SQL；此处聚合调用并返回影响行数（便于日志）。
    """
    counts: Dict[str, int] = {"image": 0, "video_analysis": 0, "video_match": 0}
    from services.image_history_db_service import image_history_db_service
    from services.video_analysis_db_service import video_analysis_db_service
    from services.video_match_service import mark_interrupted_video_match_jobs_failed

    counts["image"] = await image_history_db_service.mark_interrupted_running_as_failed(reason)
    counts["video_analysis"] = await video_analysis_db_service.mark_interrupted_running_histories_failed(reason)
    counts["video_match"] = await mark_interrupted_video_match_jobs_failed(reason)

    total = sum(counts.values())
    if total:
        log.warning(
            "启动恢复: 生图 %s 条、视频分析 %s 条、视频匹配 job %s 条已标为失败（原因: %s）",
            counts["image"],
            counts["video_analysis"],
            counts["video_match"],
            reason[:120],
        )
    return counts


__all__ = ["mark_interrupted_tasks_on_startup"]
