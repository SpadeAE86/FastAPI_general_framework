# -*- coding: utf-8 -*-
"""
由 ``frame_size``（入库 keyword：如 9:16、320:569、竖版9:16）派生横/竖屏，供索引字段 ``frame_orientation`` 与检索归一化。
"""
from __future__ import annotations

FRAME_ORIENTATION_UNKNOWN = "未知"
FRAME_ORIENTATION_PORTRAIT = "竖屏"
FRAME_ORIENTATION_LANDSCAPE = "横屏"


def infer_frame_orientation(frame_size: str) -> str:
    """
    返回 ``横屏`` | ``竖屏`` | ``未知``（与索引 keyword 一致，便于转写模板 AND / term filter）。
    """
    v = (frame_size or "").strip()
    if not v or v == FRAME_ORIENTATION_UNKNOWN:
        return FRAME_ORIENTATION_UNKNOWN
    v_lower = v.lower()
    if v in ("竖版9:16", "竖屏9:16", "竖屏", "竖版") or v_lower in ("portrait", "vertical"):
        return FRAME_ORIENTATION_PORTRAIT
    if v in ("横版16:9", "横屏16:9", "横屏", "横版") or v_lower in ("landscape", "horizontal"):
        return FRAME_ORIENTATION_LANDSCAPE
    if v == "其他比例":
        return FRAME_ORIENTATION_UNKNOWN
    if ":" in v:
        a, b = v.split(":", 1)
        try:
            w, h = int(a.strip()), int(b.strip())
            if w <= 0 or h <= 0:
                return FRAME_ORIENTATION_UNKNOWN
            if w < h:
                return FRAME_ORIENTATION_PORTRAIT
            if w > h:
                return FRAME_ORIENTATION_LANDSCAPE
            return FRAME_ORIENTATION_UNKNOWN
        except ValueError:
            return FRAME_ORIENTATION_UNKNOWN
    return FRAME_ORIENTATION_UNKNOWN
