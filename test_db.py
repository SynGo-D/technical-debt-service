"""Checks BOTH databases the service needs.  Run:  python test_db.py"""
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings


async def check(label: str, url: str, tables: list[str]) -> bool:
    engine = create_async_engine(url)

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            print(f"[ok]   {label}: connected")

            found = (await connection.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            ))).scalars().all()

            for t in tables:
                print(f"       table {t}: {'present' if t in found else 'MISSING'}")

            return True

    except Exception as e:
        print(f"[FAIL] {label}: {type(e).__name__}: {e}")
        return False

    finally:
        await engine.dispose()


async def main():
    a = await check(
        "technical-debt DB  (DATABASE_URL)",
        settings.database_url,
        ["debt_reviews", "debt_issues"],
    )
    b = await check(
        "analysis-engine DB (ANALYSIS_DATABASE_URL)",
        settings.analysis_database_url,
        ["analysis_results", "findings"],
    )
    raise SystemExit(0 if a and b else 1)


if __name__ == "__main__":
    asyncio.run(main())
