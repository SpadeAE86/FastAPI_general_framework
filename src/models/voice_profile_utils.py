from __future__ import annotations

from typing import Optional

CONFIRMED_MALE_VOICES = {
    "活力青年",
    "冷漠兄长",
    "冷脸兄长",
    "亲切青年",
    "温柔学长",
    "深夜播客",
    "东方浩然",
    "开朗弟弟",
    "冷峻上司",
    "成熟总裁",
    "傲娇精英",
    "清新沐沐",
    "爽朗小阳",
    "清新波波",
    "沉稳明仔",
    "亲切小卓",
    "阳光洋洋",
    "醇厚低音",
    "阳光青年",
    "开朗青年",
    "反卷青年",
    "质朴青年",
    "儒雅青年",
    "纨绔青年",
    "潇洒青年",
    "通用赘婿",
    "诚诚",
    "童童",
    "懒小羊",
    "智慧老者",
    "影视解说小帅",
    "解说小帅-多情感",
    "擎苍",
    "炀炀",
    "擎苍 2.0",
}

CONFIRMED_FEMALE_VOICES = {
    "灿灿 2.0",
    "灿灿",
    "超自然音色-梓梓2.0",
    "超自然音色-梓梓",
    "超自然音色-燃燃2.0",
    "超自然音色-燃燃",
    "古风少御",
    "甜宠少御",
}

MALE_NAME_HINTS = (
    "男",
    "哥",
    "叔",
    "爷",
    "公子",
    "少爷",
    "男友",
    "男生",
    "少年",
    "青年",
    "兄长",
    "学长",
    "君子",
    "将军",
    "侠客",
    "法师",
    "总裁",
    "小生",
    "弟弟",
)

FEMALE_NAME_HINTS = (
    "女",
    "姐",
    "妹",
    "姨",
    "少女",
    "女友",
    "女生",
    "学姐",
    "姐姐",
    "阿姨",
    "奶奶",
    "萝莉",
    "女王",
    "御姐",
    "公主",
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
    """Infer 1 for male and 0 for female."""

    name = voice_character or ""
    gender = _norm_gender(meta_gender)

    if name in CONFIRMED_MALE_VOICES:
        return 1
    if name in CONFIRMED_FEMALE_VOICES:
        return 0

    if gender in {"男", "male", "m", "man", "boy"}:
        return 1
    if gender in {"女", "female", "f", "woman", "girl"}:
        return 0

    male_score = sum(1 for hint in MALE_NAME_HINTS if hint in name)
    female_score = sum(1 for hint in FEMALE_NAME_HINTS if hint in name)

    if male_score > female_score:
        return 1
    if female_score > male_score:
        return 0

    return None
