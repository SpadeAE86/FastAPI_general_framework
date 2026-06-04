from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine

from config.config import *


from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel

from config.config import my_config, ENV, log

def create_url(config, async_mode=True):
    driver_type = "asyncmy" if async_mode else "pymysql"
    url = URL.create(drivername=f"mysql+{driver_type}", **config)
    return url

class DBManager:
    def __init__(self):
        log.info(f"init mysql manager")
        self.engines = {}
        self.sql_config = my_config["mysql"][ENV]
        self.main_db_url = create_url(self.sql_config)
        
        import sys
        # 架构级隔离设计：
        # 如果当前运行在 Celery 进程中，由于 Celery 会频繁产生新的 event loop，必须使用 NullPool 以免跨 loop 污染。
        # 如果运行在 FastAPI/Uvicorn 中，因为它们常驻同一个主 event loop，应该开启 QueuePool 保持高并发下的长连接复用性能。
        is_celery = "celery" in sys.argv[0].lower() or "celery" in sys.modules

        if is_celery:
            from sqlalchemy.pool import NullPool
            self.main_engine = create_async_engine(
                self.main_db_url, 
                echo=False,
                poolclass=NullPool
            )
            log.info("Initialized MySQL Manager with NullPool (Celery Worker Mode)")
        else:
            self.main_engine = create_async_engine(
                self.main_db_url, 
                echo=False,
                pool_size=10, 
                max_overflow=20,
                pool_recycle=3600
            ) 
            log.info("Initialized MySQL Manager with QueuePool (FastAPI Server Mode)")
        self.engines[self.main_db_url] = self.main_engine
        
        self.SessionLocal = async_sessionmaker(
            bind=self.main_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )

    def get_engine(self, db_url: str):
        if db_url not in self.engines:
            engine = create_async_engine(db_url, echo=False)
            self.engines[db_url] = engine
        return self.engines[db_url]
        
    async def init_db(self):
        # 导入你的所有SQLModel模型以确保它们被注册到 SQLModel.metadata
        import models.pydantic_models.db.mix_time_records
        import models.pydantic_models.db.volcovoice_sample
        async with self.main_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        log.info("Initialized Database Tables")

db_manager = DBManager()

