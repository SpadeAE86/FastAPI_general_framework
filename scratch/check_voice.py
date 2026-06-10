import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from database.mysql.mysql_manager import db_manager
from sqlalchemy import text

async def main():
    await db_manager.init_db()
    async with db_manager.get_session() as session:
        result = await session.execute(text("SELECT * FROM volcovoice_sample WHERE voice_character LIKE '%广州德哥%'"))
        rows = result.fetchall()
        if not rows:
            print("没找到 '广州德哥'")
        else:
            for r in rows:
                print(r)

if __name__ == "__main__":
    asyncio.run(main())
