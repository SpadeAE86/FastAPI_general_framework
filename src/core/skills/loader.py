# core/skills/loader.py — Skill 文件加载器
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any, List
from infra.logging.logger import logger as log
from core.skills.parser import parse_skill_markdown


class SkillLoader:
    def __init__(self, skills_dir: str | None = None) -> None:
        if skills_dir is None:
            # 默认扫描 src/skills 目录
            src_dir = Path(__file__).resolve().parent.parent.parent
            self.skills_dir = src_dir / "skills"
        else:
            self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, Dict[str, Any]] = {}

    def discover_and_load(self) -> int:
        """
        扫描 skills_dir 目录，发现所有 xxx/SKILL.md 文件并加载。
        返回成功加载的技能数量。
        """
        self._skills.clear()
        if not self.skills_dir.exists():
            log.warning(f"技能目录不存在: {self.skills_dir}")
            return 0

        count = 0
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                try:
                    name, desc, content = parse_skill_markdown(skill_file.read_text(encoding="utf-8"))
                    self._skills[name] = {
                        "name": name,
                        "description": desc,
                        "content": content,
                        "path": str(skill_file)
                    }
                    count += 1
                    log.info(f"已加载技能: {name} ({desc})")
                except Exception as e:
                    log.error(f"加载技能 {skill_file} 失败: {e}")
        return count

    def get_skill(self, name: str) -> Dict[str, Any] | None:
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list(self._skills.values())


skill_loader = SkillLoader()
skill_loader.discover_and_load()
