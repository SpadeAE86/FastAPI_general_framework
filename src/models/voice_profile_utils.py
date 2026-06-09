from __future__ import annotations

from typing import Optional

MALE_CODE_HINTS = ("_male_", "male", "zh_male", "icl_zh_male")
FEMALE_CODE_HINTS = ("_female_", "female", "zh_female", "icl_zh_female")

MALE_NAME_HINTS = (
    "男",
    "哥",
    "叔",
    "爷",
    "公子",
    "少爷",
    "青年",
    "兄长",
    "学长",
    "大叔",
    "小哥",
    "弟",
    "君",
    "先生",
    "总裁",
    "君子",
    "法师",
    "将军",
    "侠客",
)

FEMALE_NAME_HINTS = (
    "女",
    "姐",
    "姨",
    "妹",
    "嫂",
    "姑",
    "阿姨",
    "小姐",
    "萝莉",
    "少女",
    "女王",
    "女友",
    "学姐",
    "姐姐",
    "妈妈",
    "奶奶",
)


def _norm_gender(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).strip().lower()


def infer_voice_sex(
    voice_character: str,
    voice_code: str = "",
    meta_gender: Optional[str] = None,
) -> Optional[int]:
    """
    Infer 1 for male and 0 for female.

    The underlying voice catalog is messy, so we trust explicit code hints first,
    then metadata, then a lightweight name heuristic.
    """

    name = voice_character or ""
    code = voice_code or ""
    code_lower = code.lower()
    gender = _norm_gender(meta_gender)

    if any(h in code_lower for h in FEMALE_CODE_HINTS):
        return 0
    if any(h in code_lower for h in MALE_CODE_HINTS):
        return 1

    if gender in {"男", "male", "m", "man", "boy"}:
        return 1
    if gender in {"女", "female", "f", "woman", "girl"}:
        return 0

    if gender == "儿童":
        male_score = sum(1 for hint in MALE_NAME_HINTS if hint in name)
        female_score = sum(1 for hint in FEMALE_NAME_HINTS if hint in name)
        if male_score > female_score:
            return 1
        if female_score > male_score:
            return 0
        return 0

    male_score = sum(1 for hint in MALE_NAME_HINTS if hint in name)
    female_score = sum(1 for hint in FEMALE_NAME_HINTS if hint in name)

    if male_score > female_score:
        return 1
    if female_score > male_score:
        return 0

    return None
