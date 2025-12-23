from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select, insert, update, delete, Row, URL
from config.config import *
import sqlalchemy


def create_url(config, async_mode=True):
    driver_type = "asyncmy" if async_mode else "pymysql"
    url = URL.create(drivername=f"mysql+{driver_type}", **config)
    return url

class DBManager:
    def __init__(self):
        log.info(f"init mysql manager")
        self.engines = {}
        sql_config = my_config["mysql"][ENV]
        main_db_url = create_url(sql_config)
        engine = create_async_engine(main_db_url, echo=False)
        self.engines[main_db_url] = engine

    def get_engine(self, db_url: str):
        if db_url not in self.engines:
            engine = create_async_engine(db_url, echo=False)
            self.engines[db_url] = engine
        return self.engines[db_url]


db_manager = DBManager()
