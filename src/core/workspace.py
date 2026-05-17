"""
core/workspace.py — 多 workspace 配置注册表

每个 workspace 对应独立的：
  - OpenSearch index (通过 schema 类的 settings 区分)
  - MySQL 分镜卡片表 (video_analysis_shot_cards / video_analysis_shot_cards_v2)

共用的资源 (workspace-agnostic)：
  - video_analysis_video_v2       (素材行，外键源)
  - video_analysis_scene_frames   (抽帧缓存，避免重复上传)
  - video_analysis_history        (分析历史记录)

使用方式
--------
    from core.workspace import get_workspace, WORKSPACE_REGISTRY

    ws = get_workspace("v2")
    table = ws.shot_cards_table          # "video_analysis_shot_cards_v2"
    ver   = ws.shot_cards_version        # "v2"
    cls   = ws.index_class               # CarInteriorAnalysisV2
    prompt = ws.default_prompt           # 默认打标提示词
"""

from __future__ import annotations

from typing import Dict, List, Type

from pydantic import BaseModel, ConfigDict


# ─── 提示词常量（从 analysis_video.py 收归，集中管理） ─────────────────────────

_PROMPT_V1 = """你是一个专业的视频分镜分析师。
请分析视频片段，提取 object、search_tags 并进行商业价值评估。

### 1. 营销场景标签
- **场景类型**：判断属于哪种营销场景
  可选：产品展示、使用场景、情感共鸣、品牌故事、教程演示、对比评测、生活方式展示

- **目标受众**：这个画面最能打动哪类人群？
  示例：Z世代、精致妈妈、职场精英、银发族、健身达人、美食爱好者

### 2. 商业价值评估 (0-10分)
- 产品展示清晰度：画面是否适合展示产品细节
- 情感共鸣度：是否能引起观众情感共鸣
- 画面美感度：构图、光线、色彩的专业程度
- 通用适配性：是否容易与其他素材混剪
"""

_PROMPT_V2 = """你是一个专业的视频分镜分析师，同时你也了解用户在搜索视频时的习惯。
请分析这些视频片段里的画面。
【核心目标】
提取画面的客观特征、动作、空间、主体以及营销价值点，为视频检索提供高精度的标签。

【重要规则】
1. 描述 (description) 要客观：主体+动作+场景+光影。
2. 主体 (subject) 要具体：不要只写"车"，写"智己LS6"或"中控大屏"。
3. 关键词 (key_words) 和 主题 (topic) 必须从给定的枚举中选择。
4. 营销短句 (marketing_phrases) 要贴合用户搜索习惯，如"后备箱大空间"、"地库一把掉头"。
"""


# ─── 类引用解析（懒加载，避免循环导入，同时保留 WorkspaceConfig 的完整序列化能力） ──

def _resolve_index_class(name: str) -> type:
    """将 index_class_name 字符串解析为实际的 BaseIndex 子类。"""
    from models.pydantic.opensearch_index.car_interior_analysis import CarInteriorAnalysis
    from models.pydantic.opensearch_index.car_interior_analysis_v2 import CarInteriorAnalysisV2
    _registry: Dict[str, type] = {
        "CarInteriorAnalysis": CarInteriorAnalysis,
        "CarInteriorAnalysisV2": CarInteriorAnalysisV2,
    }
    cls = _registry.get(name)
    if cls is None:
        raise ValueError(f"[WorkspaceConfig] 未知 index_class_name: {name!r}，请在 _resolve_index_class 中注册")
    return cls


def _resolve_schema_class(name: str) -> type:
    """将 schema_class_name 字符串解析为实际的 Pydantic 输出 schema 类。"""
    from models.pydantic.model_output_schema.video_analysis_schema import (
        SceneAnalysisResult,
        SceneAnalysisResultV2,
    )
    _registry: Dict[str, type] = {
        "SceneAnalysisResult": SceneAnalysisResult,
        "SceneAnalysisResultV2": SceneAnalysisResultV2,
    }
    cls = _registry.get(name)
    if cls is None:
        raise ValueError(f"[WorkspaceConfig] 未知 schema_class_name: {name!r}，请在 _resolve_schema_class 中注册")
    return cls


# ─── WorkspaceConfig ───────────────────────────────────────────────────────────

class WorkspaceConfig(BaseModel):
    """
    单个 workspace 的不可变配置包。

    index_class_name / schema_class_name 使用字符串而非直接引用 class，
    原因：Pydantic 不支持将 Type[X] 序列化为 JSON；字符串字段可完整参与
    .model_dump() / .model_json_schema()，方便 API 返回和前端展示。
    运行时通过 .index_class / .schema_class property 懒加载真实 class。
    """

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    description: str

    # MySQL 分镜卡片表
    shot_cards_table: str
    shot_cards_version: str

    # OpenSearch index 名称
    opensearch_index: str

    # class 引用（字符串形式，懒解析）
    index_class_name: str   # e.g. "CarInteriorAnalysisV2"
    schema_class_name: str  # e.g. "SceneAnalysisResultV2"

    # 默认打标提示词（custom_prompt 传入时优先级更高）
    default_prompt: str

    is_default: bool = False

    @property
    def index_class(self) -> type:
        """OpenSearch index model class（懒加载，首次访问时解析）。"""
        return _resolve_index_class(self.index_class_name)

    @property
    def schema_class(self) -> type:
        """LLM 输出 schema class（懒加载，首次访问时解析）。"""
        return _resolve_schema_class(self.schema_class_name)


# ─── 注册表 ────────────────────────────────────────────────────────────────────
#
# 新增 workspace 步骤：
#   1. 在 _resolve_index_class / _resolve_schema_class 注册对应 class
#   2. 在 _WORKSPACES 追加 WorkspaceConfig(...)
#   3. 无需改动任何业务代码
#
_WORKSPACES: List[WorkspaceConfig] = [
    WorkspaceConfig(
        key="v1",
        label="经典分析 v1",
        description="基础理解 schema，字段包含 search_tags / adjective / visual_quality / marketing_tags",
        shot_cards_table="video_analysis_shot_cards",
        shot_cards_version="v1",
        opensearch_index="car_interior_analysis",
        index_class_name="CarInteriorAnalysis",
        schema_class_name="SceneAnalysisResult",
        default_prompt=_PROMPT_V1,
        is_default=True,
    ),
    WorkspaceConfig(
        key="v2",
        label="深度分析 v2",
        description=(
            "对齐 CarInteriorAnalysisV2 schema，字段包含 key_words / footage_type / "
            "shot_style / shot_type / camera_movement / scene_location / "
            "design_adjectives / function_selling_points 等"
        ),
        shot_cards_table="video_analysis_shot_cards_v2",
        shot_cards_version="v2",
        opensearch_index="car_interior_analysis_v2",
        index_class_name="CarInteriorAnalysisV2",
        schema_class_name="SceneAnalysisResultV2",
        default_prompt=_PROMPT_V2,
        is_default=False,
    ),
]

WORKSPACE_REGISTRY: Dict[str, WorkspaceConfig] = {ws.key: ws for ws in _WORKSPACES}
DEFAULT_WORKSPACE_KEY: str = next(ws.key for ws in _WORKSPACES if ws.is_default)


def get_workspace(key: str | None) -> WorkspaceConfig:
    """Return workspace config for *key*, falling back to default."""
    if key and key in WORKSPACE_REGISTRY:
        return WORKSPACE_REGISTRY[key]
    return WORKSPACE_REGISTRY[DEFAULT_WORKSPACE_KEY]


def list_workspaces() -> List[dict]:
    """Serializable list for API response（过滤内部字段，仅返回前端需要的元数据）。"""
    return [
        ws.model_dump(include={"key", "label", "description", "is_default"})
        for ws in _WORKSPACES
    ]
