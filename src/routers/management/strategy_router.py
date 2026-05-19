from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class SearchStrategyCreate(BaseModel):
    name: str
    bm25_weight: float
    vector_weight: float
    text_weights: Optional[dict] = None
    vector_weights: Optional[dict] = None
    is_default: bool = False
    use_rrf: bool = False

@router.get("/search-strategies")
async def list_search_strategies():
    """获取所有搜索策略配置"""
    from infra.storage.mysql_connector import mysql_connector
    from sqlmodel import select
    from models.sqlmodel.video_analysis import VideoAnalysisSearchStrategy
    
    await mysql_connector.ensure_init()
    
    async with mysql_connector.client() as conn:
        stmt = select(VideoAnalysisSearchStrategy).order_by(VideoAnalysisSearchStrategy.id)
        res = await conn.execute(stmt)
        strategies = res.scalars().all()
        
    return {"success": True, "strategies": [s.model_dump() for s in strategies]}

@router.post("/search-strategies")
async def save_search_strategy(req: SearchStrategyCreate):
    """保存或更新搜索策略配置"""
    from infra.storage.mysql_connector import mysql_connector
    from sqlmodel import select
    from models.sqlmodel.video_analysis import VideoAnalysisSearchStrategy
    from sqlalchemy import update
    
    await mysql_connector.ensure_init()
    
    async with mysql_connector.client() as conn:
        try:
            if req.is_default:
                await conn.execute(
                    update(VideoAnalysisSearchStrategy).values(is_default=False)
                )
                
            stmt = select(VideoAnalysisSearchStrategy).where(VideoAnalysisSearchStrategy.name == req.name)
            res = await conn.execute(stmt)
            existing = res.scalars().first()
            
            if existing:
                await conn.execute(
                    update(VideoAnalysisSearchStrategy)
                    .where(VideoAnalysisSearchStrategy.id == existing.id)
                    .values(
                        bm25_weight=req.bm25_weight,
                        vector_weight=req.vector_weight,
                        text_weights=req.text_weights,
                        vector_weights=req.vector_weights,
                        is_default=req.is_default,
                        use_rrf=req.use_rrf,
                    )
                )
            else:
                new_strategy = VideoAnalysisSearchStrategy(
                    name=req.name,
                    bm25_weight=req.bm25_weight,
                    vector_weight=req.vector_weight,
                    text_weights=req.text_weights,
                    vector_weights=req.vector_weights,
                    is_default=req.is_default,
                    use_rrf=req.use_rrf,
                )
                conn.add(new_strategy)
                
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise e
            
    return {"success": True}

@router.delete("/search-strategies/{strategy_id}")
async def delete_search_strategy(strategy_id: int):
    """删除搜索策略"""
    from infra.storage.mysql_connector import mysql_connector
    from sqlalchemy import delete
    from models.sqlmodel.video_analysis import VideoAnalysisSearchStrategy
    
    await mysql_connector.ensure_init()
    async with mysql_connector.client() as conn:
        try:
            await conn.execute(
                delete(VideoAnalysisSearchStrategy).where(VideoAnalysisSearchStrategy.id == strategy_id)
            )
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise e
            
    return {"success": True}
