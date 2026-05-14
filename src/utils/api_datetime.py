"""将 ORM 时间字段规范为 UTC ISO8601（Z），供 JSON API 使用。

``created_at`` / ``updated_at``：MySQL ``func.now()`` 在上海会话下存**上海墙钟** naive；
可能被驱动误标 ``tzinfo=UTC`` → 用 ``session_wall_to_utc_iso_z`` 统一为真实 UTC ``Z``。

``current_run_started_at``：由 Python ``datetime.now(timezone.utc)`` 写入，列内常见 **UTC 墙钟的 naive**
（数字与 UTC 一致），**不能**按上海解读，否则会比 ``created_at`` 早 8 小时，``duration_ms`` 虚高约 480 分钟。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

_SHANGHAI = timezone(timedelta(hours=8), name="CST")

_EXPLICIT_ABS_TZ = re.compile(r"(?:[zZ]\s*$)|(?:[+-]\d{2}:\d{2}\s*$)")


def parse_flexible_datetime(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        if s.endswith("Z") or s.endswith("z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def session_wall_to_utc_iso_z(dt: datetime) -> str:
    """MySQL 会话墙钟（上海）→ ``...Z``。"""
    naive = dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
    sh = naive.replace(tzinfo=_SHANGHAI)
    utc_d = sh.astimezone(timezone.utc).replace(microsecond=0)
    return utc_d.isoformat().replace("+00:00", "Z")


def utc_naive_or_aware_to_utc_iso_z(dt: datetime) -> str:
    """``current_run_started_at``：naive 一律视为 **UTC 墙钟**（与 ``now(UTC)`` 写入一致）。"""
    if dt.tzinfo is None:
        d = dt.replace(tzinfo=timezone.utc)
    else:
        d = dt.astimezone(timezone.utc)
    return d.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def dt_to_utc_iso_z(dt: Optional[datetime]) -> Optional[str]:
    """带 ``tzinfo`` 或需按上海 naive 解读时转 ``Z``（用于字符串显式偏移分支）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_SHANGHAI)
    utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return utc.isoformat().replace("+00:00", "Z")


def normalize_row_utc_iso(
    row: Dict[str, Any],
    keys: Iterable[str] = ("created_at", "updated_at", "current_run_started_at"),
) -> Dict[str, Any]:
    out = dict(row)
    for k in keys:
        if k not in out:
            continue
        v = out[k]
        if isinstance(v, datetime):
            if k == "current_run_started_at":
                out[k] = utc_naive_or_aware_to_utc_iso_z(v)
            else:
                out[k] = session_wall_to_utc_iso_z(v)
            continue
        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                continue
            check_s = raw.replace(" ", "T", 1) if (" " in raw and "T" not in raw) else raw
            coerced = parse_flexible_datetime(v)
            if coerced is None:
                continue
            if k == "current_run_started_at":
                if _EXPLICIT_ABS_TZ.search(check_s):
                    out[k] = utc_naive_or_aware_to_utc_iso_z(coerced)
                else:
                    base = coerced.replace(tzinfo=None) if coerced.tzinfo else coerced
                    out[k] = utc_naive_or_aware_to_utc_iso_z(base)
                continue
            if _EXPLICIT_ABS_TZ.search(check_s):
                out[k] = dt_to_utc_iso_z(coerced)
            else:
                base = coerced.replace(tzinfo=None) if coerced.tzinfo else coerced
                out[k] = session_wall_to_utc_iso_z(base)
    return out


def attach_image_row_duration_ms(d: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(d)
    st = (out.get("status") or "").lower()
    if st in ("running", "pending", "processing"):
        return out
    start_s = out.get("current_run_started_at") or out.get("created_at")
    end_s = out.get("updated_at")
    if not isinstance(start_s, str) or not isinstance(end_s, str):
        return out
    try:
        a = datetime.fromisoformat(start_s.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end_s.replace("Z", "+00:00"))
        ms = int((b - a).total_seconds() * 1000)
        if ms >= 0:
            out["duration_ms"] = ms
    except (ValueError, TypeError, OSError):
        pass
    return out
