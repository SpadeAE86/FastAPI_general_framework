from fastapi import APIRouter, Query
from core.workspace import list_workspaces, DEFAULT_WORKSPACE_KEY, get_workspace
from models.pydantic.opensearch_index.base_index import (
    get_vector_fields, get_searchable_fields, get_field_weights, get_vector_weights,
)

router = APIRouter()

@router.get("/workspaces")
async def get_workspaces():
    """返回当前支持的 workspace 列表（key / label / description）及默认值。"""
    return {
        "success": True,
        "workspaces": list_workspaces(),
        "default": DEFAULT_WORKSPACE_KEY,
    }

@router.get("/index-fields")
async def get_index_fields(workspace: str = Query("v2")):
    """获取指定 workspace 下索引的可用字段，用于前端动态生成权重调节滑块"""
    IndexModel = get_workspace(workspace).index_class
    text_fields = get_searchable_fields(IndexModel)
    vector_fields = get_vector_fields(IndexModel)
    return {
        "success": True,
        "text_fields": text_fields,
        "vector_fields": vector_fields,
        "text_field_weights": get_field_weights(IndexModel),
        "vector_field_weights": get_vector_weights(IndexModel),
    }
