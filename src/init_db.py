import asyncio
from sqlmodel import SQLModel
from sqlalchemy import text, inspect
from database.mysql.mysql_manager import db_manager
# 确保导入模型，使其注入到 SQLModel.metadata 中
from models.pydantic_models.db.mix_time_records import MixVideoOverallTime, MixVideoSceneTime

async def force_recreate():
    print("开始主动覆盖重建表结构...")
    print("加载到的表元数据:", SQLModel.metadata.tables.keys())
    
    async with db_manager.main_engine.begin() as conn:
        print("正在 Drop 旧表 (如果存在)...")
        await conn.execute(text("DROP TABLE IF EXISTS mix_video_scene_time;"))
        await conn.execute(text("DROP TABLE IF EXISTS mix_video_overall_time;"))
        
        print("正在执行 Create 表...")
        await conn.run_sync(SQLModel.metadata.create_all)

        # ===== 二次确认（关键）=====
        def check_tables(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            if inspector.has_table("mix_video_scene_time"):
                print("✅ mix_video_scene_time 表新建成功！")
            if inspector.has_table("mix_video_overall_time"):
                print("✅ mix_video_overall_time 表新建成功！")
            return tables

        tables = await conn.run_sync(check_tables)
    print("建表完成！你可以立刻去 Navicat 刷新查看是否存在 mix_video_overall_time 了。")

if __name__ == "__main__":
    asyncio.run(force_recreate())
