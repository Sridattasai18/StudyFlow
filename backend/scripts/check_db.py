"""Quick check script — verify DB tables exist and backend can start."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = "postgresql+asyncpg://postgres:121314@localhost:5432/studyflow"


async def main():
    engine = create_async_engine(DB_URL)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        )
        tables = [r[0] for r in result]
        print(f"Tables in studyflow DB ({len(tables)} total):")
        for t in tables:
            print(f"  ✓ {t}")
        if not tables:
            print("  ⚠ No tables found — run: python -m alembic upgrade head")
    await engine.dispose()


asyncio.run(main())
