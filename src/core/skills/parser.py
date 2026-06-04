# core/skills/parser.py — Skill 文档解析器
from __future__ import annotations
import re
from typing import Tuple


def parse_skill_markdown(content: str) -> Tuple[str, str, str]:
    """
    解析 SKILL.md 内容，提取 name, description, 和正文内容。
    返回元组 (name, description, body_content)
    """
    # 匹配 YAML frontmatter: 从开头开始，以 --- 包裹
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        raise ValueError("未找到有效的 YAML frontmatter (需要用 --- 包裹)")
    
    frontmatter = match.group(1)
    body = match.group(2)
    
    # 简单解析 name 和 description
    name = ""
    description = ""
    for line in frontmatter.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            # 去除首尾的引号
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            if k == "name":
                name = v
            elif k == "description":
                description = v
                
    if not name:
        raise ValueError("frontmatter 中缺少 name 字段")
        
    return name, description, body.strip()
