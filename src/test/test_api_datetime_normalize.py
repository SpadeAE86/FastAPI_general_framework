"""任务看板时间规范化自测：PYTHONPATH=my_agent/src python test/test_api_datetime_normalize.py"""
from __future__ import annotations

from datetime import datetime, timezone

from utils.api_datetime import (
    attach_image_row_duration_ms,
    normalize_row_utc_iso,
    session_wall_to_utc_iso_z,
    utc_naive_or_aware_to_utc_iso_z,
)


def main() -> None:
    buggy = datetime(2026, 5, 14, 13, 58, 55, tzinfo=timezone.utc)
    assert session_wall_to_utc_iso_z(buggy) == "2026-05-14T05:58:55Z"

    naive = datetime(2026, 5, 14, 13, 58, 30)
    assert session_wall_to_utc_iso_z(naive) == "2026-05-14T05:58:30Z"

    naive_utc_run = datetime(2026, 5, 14, 6, 16, 20)
    assert utc_naive_or_aware_to_utc_iso_z(naive_utc_run) == "2026-05-14T06:16:20Z"

    # 与用户 JSON 一致：created/updated 为上海墙钟，current_run 为 MySQL 里存的 UTC 墙钟 naive
    row = normalize_row_utc_iso(
        {
            "created_at": datetime(2026, 5, 14, 14, 16, 20),
            "updated_at": datetime(2026, 5, 14, 14, 16, 38),
            "current_run_started_at": datetime(2026, 5, 14, 6, 16, 20),
        }
    )
    assert row["created_at"] == "2026-05-14T06:16:20Z"
    assert row["updated_at"] == "2026-05-14T06:16:38Z"
    assert row["current_run_started_at"] == "2026-05-14T06:16:20Z"
    assert attach_image_row_duration_ms({**row, "status": "success"}).get("duration_ms") == 18_000

    row_no_run = normalize_row_utc_iso(
        {
            "created_at": datetime(2026, 5, 14, 14, 16, 20),
            "updated_at": datetime(2026, 5, 14, 14, 16, 38),
        }
    )
    assert attach_image_row_duration_ms({**row_no_run, "status": "success"}).get("duration_ms") == 18_000

    row3 = normalize_row_utc_iso(
        {"created_at": "2026-05-14T05:58:30Z", "updated_at": "2026-05-14T05:58:55Z"}
    )
    assert row3["created_at"] == "2026-05-14T05:58:30Z"
    assert row3["updated_at"] == "2026-05-14T05:58:55Z"

    print("api_datetime normalize: all assertions passed")


if __name__ == "__main__":
    main()
