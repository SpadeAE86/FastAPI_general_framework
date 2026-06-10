from sqlalchemy import URL, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from config.config import ENV, log, my_config
from models.voice_profile_utils import infer_voice_sex


def create_url(config, async_mode=True):
    driver_type = "asyncmy" if async_mode else "pymysql"
    url = URL.create(drivername=f"mysql+{driver_type}", **config)
    return url


class DBManager:
    def __init__(self):
        log.info("init mysql manager")
        self.engines = {}
        self.sql_config = my_config["mysql"][ENV]
        self.main_db_url = create_url(self.sql_config)

        import sys

        is_celery = "celery" in sys.argv[0].lower() or "celery" in sys.modules

        if is_celery:
            from sqlalchemy.pool import NullPool

            self.main_engine = create_async_engine(
                self.main_db_url,
                echo=False,
                poolclass=NullPool,
            )
            log.info("Initialized MySQL Manager with NullPool (Celery Worker Mode)")
        else:
            self.main_engine = create_async_engine(
                self.main_db_url,
                echo=False,
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600,
            )
            log.info("Initialized MySQL Manager with QueuePool (FastAPI Server Mode)")

        self.engines[self.main_db_url] = self.main_engine

        self.SessionLocal = async_sessionmaker(
            bind=self.main_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    def get_engine(self, db_url: str):
        if db_url not in self.engines:
            engine = create_async_engine(db_url, echo=False)
            self.engines[db_url] = engine
        return self.engines[db_url]

    async def _ensure_volcovoice_sample_columns(self):
        async with self.main_engine.begin() as conn:
            def _get_columns(sync_conn):
                inspector = inspect(sync_conn)
                if not inspector.has_table("volcovoice_sample"):
                    return set()
                return {column["name"] for column in inspector.get_columns("volcovoice_sample")}

            existing_columns = await conn.run_sync(_get_columns)
            if "voice_model_type" not in existing_columns:
                await conn.execute(text("ALTER TABLE volcovoice_sample ADD COLUMN voice_model_type VARCHAR(255) NULL"))
            if "age_type" not in existing_columns:
                await conn.execute(text("ALTER TABLE volcovoice_sample ADD COLUMN age_type VARCHAR(255) NULL"))
            if "sex" not in existing_columns:
                await conn.execute(text("ALTER TABLE volcovoice_sample ADD COLUMN sex INT NULL"))
            if "is_enabled" not in existing_columns:
                await conn.execute(text("ALTER TABLE volcovoice_sample ADD COLUMN is_enabled TINYINT(1) NOT NULL DEFAULT 1"))
            if "note" not in existing_columns:
                await conn.execute(text("ALTER TABLE volcovoice_sample ADD COLUMN note TEXT NULL"))
            if "priority" not in existing_columns:
                await conn.execute(text("ALTER TABLE volcovoice_sample ADD COLUMN priority INT NOT NULL DEFAULT 0"))
            if "voice_type" in existing_columns:
                await conn.execute(text("ALTER TABLE volcovoice_sample DROP COLUMN voice_type"))

            # Clean up/default NULL values in existing records
            await conn.execute(text(
                "UPDATE volcovoice_sample SET voice_model_type = 'small' "
                "WHERE voice_character = '天才少女' AND (voice_model_type IS NULL OR voice_model_type = '')"
            ))
            await conn.execute(text(
                "UPDATE volcovoice_sample SET voice_model_type = 'big' "
                "WHERE voice_model_type IS NULL OR voice_model_type = ''"
            ))

            # Migrate age_type and sex using voice_enums_meta
            from models.voice_enums_meta import voice_enums_meta
            result = await conn.execute(text("SELECT id, voice_character, voice_code FROM volcovoice_sample"))
            rows = result.fetchall()
            for r_id, char_name, voice_code in rows:
                meta = voice_enums_meta.get(char_name)
                age = meta.get('age') if meta else None
                sex_val = infer_voice_sex(char_name, voice_code, meta.get('gender') if meta else None)
                if meta:
                    await conn.execute(
                        text("UPDATE volcovoice_sample SET age_type = :age_type, sex = :sex WHERE id = :id"),
                        {"age_type": age, "sex": sex_val, "id": r_id}
                    )

    async def init_db(self):
        import models.pydantic_models.db.mix_time_records
        import models.pydantic_models.db.volcovoice_sample

        async with self.main_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        await self._ensure_volcovoice_sample_columns()
        log.info("Initialized Database Tables")



db_manager = DBManager()
