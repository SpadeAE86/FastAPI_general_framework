import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from database.mysql.mysql_manager import db_manager
from sqlalchemy import text

async def main():
    async with db_manager._engine.begin() as conn:
        result = await conn.execute(text("SELECT * FROM volcovoice_sample WHERE voice_character LIKE '%德哥%'"))
        rows = result.fetchall()
        if not rows:
            print("❌ 数据库中没找到 '广州德哥' 的 sample")
        else:
            print("✅ 找到数据：")
            for r in rows:
                print(r)

if __name__ == "__main__":
    db_manager._is_initialized = True  # skip init_db block
    asyncio.run(main())
